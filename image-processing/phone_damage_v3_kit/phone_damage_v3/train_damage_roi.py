"""Train and validate phone-body + global-context/native-detail segmentation."""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import time

import numpy as np
from PIL import Image, ImageDraw, ImageOps
import torch

from .phone_data import ROOT, digest
from .phone_damage_roi import (ARCHITECTURE, ContextDamageUNet, ROIPatchSource,
                              load_manifest, roi_loss, roi_probability, tensors)
from .phone_semantic import overlay, pixel_counts, scores


DEFAULT_MANIFEST = ROOT/'my_data/datasets/phone_damage_roi_v3_20261020/manifest.json'
THRESHOLDS = [.3, .4, .5, .6, .65, .7, .75, .8, .85, .9]


def write_json(path, value):
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def load_model(path, device, initialize=False):
    saved = torch.load(path, map_location='cpu', weights_only=True)
    model = ContextDamageUNet(pretrained=False)
    if saved['architecture'] == ARCHITECTURE:
        model.load_state_dict(saved['state_dict'])
    elif initialize and saved['architecture'] == 'resnet18_unet_native_binary_v1':
        incompatible = model.load_state_dict(saved['state_dict'], strict=False)
        if set(incompatible.missing_keys) != {'context_fusion.weight'} or incompatible.unexpected_keys:
            raise ValueError('Unexpected initialization mismatch.')
    else:
        raise ValueError('Incompatible damage checkpoint.')
    return model.to(device).eval(), saved


def save_checkpoint(path, model, args, data, metric, epoch):
    saved = dict(architecture=ARCHITECTURE, state_dict=model.state_dict(),
                 patch_size=args.patch_size, overlap=args.overlap, context_size=data['context_size'],
                 body_margin=args.body_margin, threshold=metric.get('threshold', .5),
                 source_data=str(args.manifest.resolve()), manifest_sha256=digest(args.manifest),
                 phone_model_sha256=data['phone_model_sha256'], metric=metric, epoch=epoch,
                 scope='full_phone_damage_with_body_and_aligned_context', seed=args.seed)
    tmp = path.with_suffix('.tmp')
    torch.save(saved, tmp)
    tmp.replace(path)


def optimizer_for(model, lr):
    encoder, decoder = [], []
    for name, param in model.named_parameters():
        (encoder if name.startswith(('stem.', 'layers.')) else decoder).append(param)
    return torch.optim.AdamW([dict(params=encoder, lr=lr*.1), dict(params=decoder, lr=lr)], weight_decay=1e-4)


def train_step(model, samples, optimizer, device, rng=None):
    model.train()
    optimizer.zero_grad(set_to_none=True)
    losses = []
    for sample in samples:
        image, context, boxes, target = tensors([sample], device, rng)
        loss = roi_loss(model(image, context=context, boxes=boxes), target, 1.5)
        if not torch.isfinite(loss):
            raise ValueError('Non-finite training loss.')
        (loss/len(samples)).backward()
        losses.append(float(loss.detach()))
    torch.nn.utils.clip_grad_norm_(model.parameters(), 5.)
    optimizer.step()
    return float(np.mean(losses))


def proposed_samples(source, rng, size):
    first = source.positive[int(rng.integers(len(source.positive)))]
    second = source.positive[int(rng.integers(len(source.positive)))]
    return [source.sample(rng, size, 'positive', first),
            source.sample(rng, size, 'positive', second),
            source.sample(rng, size, 'healthy_damage', first),
            source.sample(rng, size, 'normal')]


@torch.inference_mode()
def fixed_metrics(model, samples, device):
    model.eval()
    total, positive_dice, loss_values = dict(tp=0, fp=0, fn=0), [], []
    predictions = []
    for sample in samples:
        image, context, boxes, target = tensors([sample], device)
        logits = model(image, context=context, boxes=boxes)
        loss_values.append(float(roi_loss(logits, target)))
        pred = logits[0, 0].sigmoid().cpu().numpy() >= .5
        count = pixel_counts(pred, sample['target'])
        for k in total:
            total[k] += count[k]
        if (sample['target'] == 1).any():
            positive_dice.append(scores(count)['damage_dice'])
        predictions.append(pred)
    return dict(**scores(total), macro_positive_patch_dice=float(np.mean(positive_dice)),
                loss=float(np.mean(loss_values))), predictions


def save_fixed_panel(samples, predictions, path):
    panel = Image.new('RGB', (900, len(samples)*325), 'white')
    for i, (sample, pred) in enumerate(zip(samples, predictions)):
        views = [Image.fromarray(sample['rgb']), overlay(sample['rgb'], sample['target'] == 1),
                 overlay(sample['rgb'], pred & (sample['target'] != 255))]
        for j, view in enumerate(views):
            panel.paste(ImageOps.contain(view, (300, 300)), (j*300, i*325+25))
        ImageDraw.Draw(panel).text((5, i*325+4), sample['meta']['id']+' RGB | target | prediction', fill='black')
    panel.save(path, quality=92)


@torch.inference_mode()
def evaluate(model, records, device, args, data, out=None):
    total = [dict(tp=0, fp=0, fn=0) for _ in THRESHOLDS]
    all_rows = []
    previews = {}
    preview_ids = {'d012', 'd014', 'd033', 'd106', 'd155', 'n017'}
    for row in records:
        rgb = np.load(row['rgb_cache'], mmap_mode='r')
        with Image.open(row['mask']) as im:
            target = np.array(im.convert('L')) > 0
        if row.get('_forced_normal'):
            target[:] = False
        with Image.open(row['body']) as im:
            body = np.array(im.convert('L')) > 0
        probability = roi_probability(model, rgb, body, args.patch_size, args.overlap,
                                      data['context_size'], device, args.body_margin)
        target_pixels = int(target.sum())
        bins = np.asarray([-np.inf, *THRESHOLDS, np.inf], dtype=np.float32)
        pos_hist = np.histogram(probability[target], bins=bins)[0]
        neg_hist = np.histogram(probability[~target], bins=bins)[0]
        tp = np.cumsum(pos_hist[::-1])[::-1][1:]
        fp = np.cumsum(neg_hist[::-1])[::-1][1:]
        curve = []
        for i, t in enumerate(THRESHOLDS):
            count = dict(tp=int(tp[i]), fp=int(fp[i]), fn=target_pixels-int(tp[i]))
            for key in count:
                total[i][key] += count[key]
            curve.append(dict(threshold=t, **count, **scores(count), predicted_pixels=int(tp[i]+fp[i])))
        all_rows.append(dict(id=row['annotation_id'], kind=row['kind'], target_pixels=target_pixels, curve=curve))
        if out is not None and row['annotation_id'] in preview_ids:
            # Preview resize is ONLY for display; all scores above use original pixels.
            preview_rgb = ImageOps.contain(Image.fromarray(np.asarray(rgb)), (800, 800))
            size = preview_rgb.size
            previews[row['annotation_id']] = (np.array(preview_rgb),
                np.array(Image.fromarray(target.astype(np.uint8)).resize(size, Image.Resampling.NEAREST)) > 0,
                np.array(Image.fromarray(probability).resize(size, Image.Resampling.BILINEAR)))
        print(f'Validation {row["annotation_id"]}', flush=True)
    curve = []
    for i, t in enumerate(THRESHOLDS):
        positives = [r['curve'][i]['damage_dice'] for r in all_rows if r['kind'] == 'damaged']
        normals = [r for r in all_rows if r['kind'] == 'normal']
        alarms = sum(r['curve'][i]['predicted_pixels'] >= 200 for r in normals)
        metric = dict(threshold=t, **scores(total[i]), counts=total[i],
                      macro_damaged_dice=float(np.mean(positives)), normal_images=len(normals),
                      normal_false_positive_images=alarms, normal_false_positive_rate=alarms/len(normals) if normals else None)
        metric['selection_score'] = .5*(metric['damage_dice']+metric['macro_damaged_dice'])
        curve.append(metric)
    feasible = [m for m in curve if m['normal_false_positive_images'] == 0 and m['normal_images'] > 0]
    if feasible:
        selected = dict(max(feasible, key=lambda m: m['selection_score']), constraint_satisfied=True)
    else:
        selected = dict(min(curve, key=lambda m: (m['normal_false_positive_images'], -m['selection_score'])), constraint_satisfied=False)
    result = dict(selected=selected, threshold_curve=curve, images=all_rows,
                  target_policy='Full unchanged original GT; excluded ROI pixels still count as FN.',
                  selection_policy='Mean of micro and macro damage Dice among thresholds with zero normal alarms; infeasible fallback explicitly flagged.')
    if out is not None:
        dest = out/'val_previews'
        dest.mkdir(exist_ok=True)
        for rid, (rgb, gt, prob) in previews.items():
            overlay(rgb, prob >= selected['threshold']).save(dest/(rid+'_pred.jpg'), quality=92)
            overlay(rgb, gt).save(dest/(rid+'_gt.jpg'), quality=92)
    return result


def run_overfit(model, source, device, args, data, out, rng):
    ids = ['d016', 'd053', 'd107', 'd244', 'n001', 'n024']
    by_id = {r['annotation_id']:r for r in source.records}
    samples = [source.sample(rng, args.patch_size, 'positive' if by_id[rid]['kind']=='damaged' else 'normal', by_id[rid]) for rid in ids]
    write_json(out/'fixed_patches.json', dict(type='Training memorization diagnostic only; not generalization.', samples=[s['meta'] for s in samples]))
    optimizer = optimizer_for(model, args.lr)
    history = []
    initial, _ = fixed_metrics(model, samples, device)
    write_json(out/'initial.json', initial)
    for step in range(args.steps+1):
        if step:
            train_step(model, [samples[(step-1)%len(samples)]], optimizer, device)
        if step % 12 == 0 or step == args.steps:
            metric, preds = fixed_metrics(model, samples, device)
            history.append(dict(step=step, **metric))
            write_json(out/'history.json', history)
            save_fixed_panel(samples, preds, out/'comparison.jpg')
            print(json.dumps(history[-1]), flush=True)
    passed = history[-1]['macro_positive_patch_dice'] >= .65 and history[-1]['loss'] < initial['loss']
    write_json(out/'diagnostic.json', dict(passed=passed, initial=initial, final=history[-1],
        max_gpu_memory_mib=torch.cuda.max_memory_allocated()/1024**2 if device.type=='cuda' else None))
    save_checkpoint(out/'diagnostic.pt', model, args, data, history[-1], args.steps)
    if not passed:
        raise RuntimeError('Memorization diagnostic did not pass; inspect before long training.')


def run_train(model, source, device, args, data, out, rng):
    validation = [r for r in data['records'] if r['split']=='val']
    optimizer = optimizer_for(model, args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, args.epochs, eta_min=args.lr*.01)
    history, best_score, stale = [], -1., 0
    if not args.skip_initial_val:
        result = evaluate(model, validation, device, args, data, out)
        write_json(out/'initial_validation.json', result)
        if result['selected']['constraint_satisfied']:
            best_score = result['selected']['selection_score']
            save_checkpoint(out/'best.pt', model, args, data, result['selected'], 0)
            write_json(out/'best_validation.json', dict(epoch=0, **result))
        print('Initial validation '+json.dumps(result['selected']), flush=True)
    for epoch in range(1, args.epochs+1):
        started = time.monotonic()
        losses, sampling = [], Counter()
        for step in range(args.steps_per_epoch):
            samples = proposed_samples(source, rng, args.patch_size)
            for sample in samples:
                sampling[sample['meta']['mode']] += 1
                sampling['actual_nonempty' if sample['meta']['positive_pixels'] else 'actual_empty'] += 1
            losses.append(train_step(model, samples, optimizer, device, rng))
            if (step+1) % 8 == 0:
                print(f'Epoch {epoch}/{args.epochs}, update {step+1}/{args.steps_per_epoch}, loss={np.mean(losses):.4f}', flush=True)
        scheduler.step()
        row = dict(epoch=epoch, loss=float(np.mean(losses)), sampling=dict(sampling),
                   training_seconds=time.monotonic()-started,
                   gpu_memory_mib=torch.cuda.max_memory_allocated()/1024**2 if device.type=='cuda' else None)
        if epoch % args.val_every == 0 or epoch == args.epochs:
            result = evaluate(model, validation, device, args, data, out)
            row.update(result['selected'])
            write_json(out/'last_validation.json', dict(epoch=epoch, **result))
            if result['selected']['selection_score'] > best_score and result['selected']['constraint_satisfied']:
                best_score = result['selected']['selection_score']
                stale = 0
                save_checkpoint(out/'best.pt', model, args, data, result['selected'], epoch)
                write_json(out/'best_validation.json', dict(epoch=epoch, **result))
                best_previews = out/'best_previews'
                best_previews.mkdir(exist_ok=True)
                import shutil
                for image in (out/'val_previews').glob('*.jpg'):
                    shutil.copy2(image, best_previews/image.name)
            else:
                stale += 1
        save_checkpoint(out/'last.pt', model, args, data, row, epoch)
        state = dict(epoch=epoch, model=model.state_dict(), optimizer=optimizer.state_dict(),
                     scheduler=scheduler.state_dict(), rng=rng.bit_generator.state,
                     torch_rng=torch.get_rng_state(), cuda_rng=torch.cuda.get_rng_state() if device.type=='cuda' else None,
                     history=history+[row], best_score=best_score, stale=stale)
        torch.save(state, out/'training_state.pt')
        history.append(row)
        write_json(out/'history.json', history)
        print(json.dumps(row), flush=True)
        if stale >= args.patience:
            print('Early stopping after validation did not improve.', flush=True)
            break
    write_json(out/'completion.json', dict(completed=True, epochs=len(history), best_score=best_score,
                                          best_checkpoint_exists=(out/'best.pt').exists()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['overfit', 'train', 'evaluate'])
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--model', type=Path, default=ROOT/'models/screen_cracks_v1/model.pt')
    parser.add_argument('--name', required=True)
    parser.add_argument('--patch-size', type=int, default=512)
    parser.add_argument('--overlap', type=int, default=128)
    parser.add_argument('--body-margin', type=float, default=0)
    parser.add_argument('--epochs', type=int, default=24)
    parser.add_argument('--steps-per-epoch', type=int, default=32)
    parser.add_argument('--steps', type=int, default=96)
    parser.add_argument('--val-every', type=int, default=3)
    parser.add_argument('--patience', type=int, default=4)
    parser.add_argument('--lr', type=float, default=.0001)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--skip-initial-val', action='store_true')
    parser.add_argument('--device', default='auto')
    args = parser.parse_args()
    if (args.patch_size < 64 or args.patch_size % 32 or not 0 <= args.overlap < args.patch_size
            or not 0 <= args.body_margin <= .05 or min(args.epochs,args.steps_per_epoch,args.steps,args.val_every,args.patience)<1
            or args.lr <= 0 or Path(args.name).name != args.name or args.name in ('.','..')):
        parser.error('Invalid arguments.')
    out = ROOT/'runs/damage_roi'/args.name
    if out.exists():
        parser.error('Run exists; choose another name.')
    torch.set_num_threads(4)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device(('cuda:0' if torch.cuda.is_available() else 'cpu') if args.device=='auto' else args.device)
    data = load_manifest(args.manifest)
    rng = np.random.default_rng(args.seed)
    model, _ = load_model(args.model, device, initialize=True)
    source = ROIPatchSource([r for r in data['records'] if r['split']=='train'], data['context_size'], data['training_margin'])
    out.mkdir(parents=True)
    write_json(out/'experiment.json', dict(architecture=ARCHITECTURE, arguments={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},
        device=str(device), torch=str(torch.__version__), dataset_stats=data['stats'],
        manifest_sha256=digest(args.manifest), initial_model_sha256=digest(args.model),
        phone_model_sha256=data['phone_model_sha256'], precision='FP32', pos_weight=1.5,
        source_code_sha256={p:digest(ROOT/p) for p in ['phone_damage_roi.py','train_damage_roi.py','prepare_damage_roi.py']},
        sampling='50% positive, 25% healthy regions of damage images, 25% normals; exact target retained.',
        validation='Original full-size GT; no test images; frozen cached phone masks; strict normal-alarm constraint.'))
    if args.command == 'overfit':
        run_overfit(model, source, device, args, data, out, rng)
    elif args.command == 'train':
        run_train(model, source, device, args, data, out, rng)
    else:
        result = evaluate(model, [r for r in data['records'] if r['split']=='val'], device, args, data, out)
        write_json(out/'evaluation.json', result)
        print(json.dumps(result['selected']), flush=True)


if __name__ == '__main__':
    main()
