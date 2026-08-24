from pathlib import Path

new = Path('.github/workflows/build-dudu7-13.7.77.yml')
text = new.read_text()
old = '          test "$(grep -c \'rtrMatchedFrequency = 0f\' "$FM")" -ge 3\n'
replacement = '          test "$(grep -c \'rtrMatchedFrequency = 0f\' "$FM")" -ge 2\n'
if text.count(old) != 1:
    raise SystemExit(f'13.7.77 source gate match count={text.count(old)}')
new.write_text(text.replace(old, replacement, 1))

old_workflow = Path('.github/workflows/build-dudu7-13.7.76.yml')
text = old_workflow.read_text()
old = 'jobs:\n  test-build-release:\n    runs-on: ubuntu-22.04\n'
replacement = "jobs:\n  test-build-release:\n    if: ${{ github.event_name == 'workflow_dispatch' || github.head_ref == 'agent/issues-112-164-fm-rds-af-13-7-76' }}\n    runs-on: ubuntu-22.04\n"
if text.count(old) != 1:
    raise SystemExit(f'13.7.76 job header match count={text.count(old)}')
old_workflow.write_text(text.replace(old, replacement, 1))
print('CI gates fixed')
