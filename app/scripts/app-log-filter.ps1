function Test-VisibleAppLog {
    param(
        [string]$Line,
        [switch]$ShowNativeLogs,
        [switch]$ShowGraphicsNoise
    )
    # Flutter/ADB may include ANSI colour codes or extra spaces around the tag.
    $plain = $Line -replace ([char]27 + '\[[0-9;]*[A-Za-z]'), ''
    if ($plain -notmatch '^\s*(?<level>[VDIWEF])/(?<tag>[^(:]+?)\s*\(\s*\d+\s*\)\s*:\s*(?<message>.*)$') {
        # Keep build output, Flutter tool errors and multiline stack traces.
        return $true
    }
    $level, $tag, $message = $matches.level, $matches.tag.Trim(), $matches.message
    if ($tag -eq 'flutter') { return $true }
    $graphicsNoise = ($tag -in @('gralloc4', 'mali_config')) -and
        ($message -match '^(?:Empty SMPTE 2094-40 data|@get_buffer_dataspace_setting: update dataspace|@set_metadata: update dataspace)')
    if ($graphicsNoise) { return [bool]$ShowGraphicsNoise }
    if ($ShowNativeLogs) { return $true }
    # The focused console retains errors/crashes. Every line, including hidden
    # native warnings and debug output, is saved before this filter is applied.
    return $level -in @('E', 'F') -or $tag -eq 'System.err'
}
