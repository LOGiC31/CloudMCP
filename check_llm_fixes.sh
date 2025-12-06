#!/bin/bash
# Script to check LLM fix results

echo "🔍 Checking LLM Fix Results"
echo "============================"
echo ""

# Get current resource status
echo "📊 Current Resource Status:"
echo "---------------------------"
curl -s http://localhost:8000/api/resources | python3 -m json.tool | grep -E '"name"|"status"' | paste - - | sed 's/.*"name": "\([^"]*\)".*"status": "\([^"]*\)".*/  \1: \2/'
echo ""

# Get latest fix evaluation
echo "📝 Latest Fix Evaluation:"
echo "-------------------------"
LATEST_FIX=$(curl -s http://localhost:8000/api/fixes | python3 -c "import sys, json; fixes = json.load(sys.stdin); print(json.dumps(fixes[0] if fixes else {}, indent=2))" 2>/dev/null)

if [ -n "$LATEST_FIX" ] && [ "$LATEST_FIX" != "{}" ]; then
    echo "$LATEST_FIX" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  Fix ID: {data.get('id', 'N/A')}\")
print(f\"  Status: {data.get('execution_status', 'N/A')}\")
print(f\"  Total Attempts: {data.get('total_attempts', 1)}\")
print(f\"  Final Status: {data.get('final_status', 'N/A')}\")
print(f\"  Root Cause: {data.get('fix_plan', {}).get('root_cause', 'N/A')[:100]}...\")

# Show attempt summary
attempts = data.get('attempts', [])
if len(attempts) > 1:
    print(f\"  Retry Summary:\")
    for i, attempt in enumerate(attempts, 1):
        status = attempt.get('execution_status', 'UNKNOWN')
        tools = attempt.get('tools_used', [])
        resolved = attempt.get('issues_resolved', False)
        icon = '✅' if status == 'SUCCESS' else '❌'
        print(f\"    {icon} Attempt {i}: {status} (Tools: {', '.join(tools) if tools else 'none'}, Resolved: {resolved})\")
else:
    steps = data.get('tool_results', [])
    print(f\"  Steps Executed: {len(steps)}\")
    print(f\"  Successful: {sum(1 for r in steps if r.get('result', {}).get('success'))}\")
    print(f\"  Failed: {sum(1 for r in steps if r.get('result', {}).get('success') == False)}\")
"
else
    echo "  No fixes found"
fi
echo ""

# Compare before/after metrics
echo "📈 Before vs After Comparison:"
echo "-------------------------------"
curl -s http://localhost:8000/api/fixes | python3 -c "
import sys, json
fixes = json.load(sys.stdin)
if fixes:
    fix = fixes[0]
    before = fix.get('before_metrics', {})
    after = fix.get('after_metrics', {})
    
    print('  Resource Status Changes:')
    for resource in sorted(set(list(before.keys()) + list(after.keys()))):
        before_status = before.get(resource, {}).get('status', 'UNKNOWN')
        after_status = after.get(resource, {}).get('status', 'UNKNOWN')
        if before_status != after_status:
            # Show improvement (DEGRADED/FAILED → HEALTHY) as ✅
            # Show degradation (HEALTHY → DEGRADED/FAILED) as ❌
            if before_status in ['DEGRADED', 'FAILED'] and after_status == 'HEALTHY':
                print(f\"    ✅ {resource}: {before_status} → {after_status}\")
            elif before_status == 'HEALTHY' and after_status in ['DEGRADED', 'FAILED']:
                print(f\"    ❌ {resource}: {before_status} → {after_status}\")
            else:
                # Status changed but not clearly better/worse
                print(f\"    ⚠️  {resource}: {before_status} → {after_status}\")
        elif after_status == 'HEALTHY':
            print(f\"    ✓ {resource}: {after_status} (unchanged)\")
        elif after_status in ['DEGRADED', 'FAILED']:
            print(f\"    ⚠️  {resource}: {after_status} (unchanged - still needs fixing)\")
    
    # Show retry information if available
    attempts = fix.get('attempts', [])
    if len(attempts) > 1:
        print('')
        print('  Retry Details:')
        for attempt in attempts:
            num = attempt.get('attempt_number', '?')
            status = attempt.get('execution_status', 'UNKNOWN')
            resolved = attempt.get('issues_resolved', False)
            failed_resources = attempt.get('failed_resources', [])
            icon = '✅' if status == 'SUCCESS' else '❌'
            print(f\"    {icon} Attempt {num}: {status} (Issues Resolved: {resolved})\")
            if failed_resources:
                for fr in failed_resources:
                    print(f\"      - {fr.get('resource')}: {fr.get('reason', '')}\")
" 2>/dev/null || echo "  Could not parse fix data"
echo ""

# Check LLM interactions
echo "🤖 LLM Interactions:"
echo "--------------------"
curl -s http://localhost:8000/api/llm/interactions | python3 -c "
import sys, json
interactions = json.load(sys.stdin)
if interactions:
    latest = interactions[0]
    print(f\"  Latest Interaction ID: {latest.get('id', 'N/A')}\")
    print(f\"  Tokens Used: {latest.get('tokens_used', 'N/A')}\")
    print(f\"  Model: {latest.get('model', 'N/A')}\")
    print(f\"  Response Length: {len(latest.get('response', ''))} chars\")
else:
    print('  No interactions found')
" 2>/dev/null || echo "  Could not fetch interactions"
echo ""

echo "✅ Check complete!"

