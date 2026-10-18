from model.metrics import calibrate_normal_threshold, false_negative_count, predictions_from_normal_probabilities


def test_threshold_calibration_improves_defective_f1() -> None:
    labels = [0, 0, 1, 1]
    normal_probabilities = [0.4, 0.6, 0.7, 0.8]
    threshold, metrics = calibrate_normal_threshold(labels, normal_probabilities)
    assert threshold == 0.7
    assert metrics["f1_defective"] == 1.0
    assert predictions_from_normal_probabilities(normal_probabilities, threshold) == labels


def test_false_negative_count() -> None:
    assert false_negative_count([0, 0, 1], [1, 0, 1]) == 1
