# TrailBuddy Prompt Behavior Test

This document demonstrates the expected behavior after the system prompt improvements.

## Questions that SHOULD use tools (about user's personal data):

✅ "How many hikes have I completed?"
✅ "What was my longest hike?"
✅ "Show me all hikes I did in May 2026"
✅ "Which hikes did I mention feeling tired?"
✅ "What's my total distance hiked?"
✅ "Tell me about my hike to Horgen"
✅ "What was the hardest hike I've done?"

**Expected**: Tool calls to `query_hikes_db` or `search_hike_notes`

---

## Questions that should NOT use tools (general advice):

❌ "What should I bring on a hike?"
❌ "How do I prevent blisters while hiking?"
❌ "What's a good beginner hike distance?"
❌ "When is the best time of day to hike?"
❌ "Hello! What can you help me with?"
❌ "How do I prepare for a 10km hike?"
❌ "What are good hiking shoes?"
❌ "Tell me about hiking in general"
❌ "Is elevation gain of 500m difficult?"

**Expected**: Direct answers WITHOUT tool calls

---

## Testing

To verify this behavior:
1. Start the Streamlit app
2. Go to "Chat with TrailBuddy"
3. Ask general questions like "What should I pack for a hike?"
4. Verify the response is immediate and doesn't show tool usage
5. Then ask personal questions like "How many hikes have I done?"
6. Verify this DOES show tool usage in the UI

The key improvement: TrailBuddy should now act as a general hiking companion for advice, and only query your data when you specifically ask about YOUR hiking history.
