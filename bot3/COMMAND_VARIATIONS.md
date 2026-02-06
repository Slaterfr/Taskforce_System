# Discord Bot - Recognized Command Variations

This document shows all the different ways you can phrase commands that the bot will understand.

## Two Ways to Command
You can interact with the bot in two ways:
1. **Slash Command:** `/tf [your command]`
2. **Mention:** `@Cortex [your command] - The one used in this channel as its the only one that works inside of a message with content (the format)`

Both work exactly the same way!

**Examples:**
- `/tf log a raid for x`
- `@Cortex log a raid for x`

## List Members Commands

### Show All Members
```
/tf show all members
/tf list all members
/tf show everyone
/tf list everyone
/tf show all
```

### Filter by Rank (Generals)
```
/tf show all generals
/tf list all generals
/tf show generals
/tf list generals
/tf show all General
```

### Filter by Rank (Commanders)
```
/tf show all commanders
/tf list all commanders
/tf show commanders
/tf list commanders
/tf show all Commander
```

### Other Ranks
Works with any rank: `Aspirant, Novice, Adept, Crusader, Paladin, Exemplar, Prospect, Commander, Marshal, General, Chief General`

**Examples:**
- `/tf show all paladins`
- `/tf list exemplars`
- `/tf show all crusaders`

---

## 👤 Get Member Info

```
/tf what rank is [name]?
/tf who is [name]?
/tf info on [name]
/tf show [name]
/tf tell me about [name]
```

---

## 🔼 Change Member Rank

```
/tf change [name]'s rank to [rank]
/tf promote [name] to [rank]
/tf make [name] a [rank]
/tf set [name] to [rank]
/tf [name] is now [rank]
```

**Examples:**
- `/tf change John's rank to Commander`
- `/tf promote Sarah to General`
- `/tf make Mike a Paladin`

---

## ➕ Add Member

```
/tf add [name]
/tf add member [name]
/tf new member [name]
/tf add [name] as [rank]
```

**Examples:**
- `/tf add John`
- `/tf add member Sarah as Aspirant`
- `/tf new member Mike`

---

## ➖ Remove Member

```
/tf remove [name]
/tf delete [name]
/tf kick [name]
/tf remove member [name]
```

---

## 📝 Log Activity

```
/tf log [activity] for [name]
/tf [name] did a [activity]
/tf record [activity] for [name]
/tf add [activity] for [name]
```

**Activity Types:** Raid, Patrol, Training, Mission, Tryout, Canceled Training, Cancelled Tryout

**Examples:**
- `/tf log raid for John`
- `/tf Sarah did a patrol`
- `/tf record training for Mike`

### Logging Cancelled Activities (IMPORTANT)
When logging a cancelled activity, be very specific to avoid it being logged as a normal activity.
Use the phrase: **"Log ONLY a cancelled [activity]..."**

**Examples:**
- `/tf log ONLY a cancelled training for Clicky`
- `@Cortex log ONLY a cancelled training for Clicky`
- `/tf log ONLY a cancelled tryout for Lauv`
- `@Cortex log ONLY a cancelled tryout for Lauv`

This ensures the bot knows exactly what you mean and doesn't make mistakes!


## 💡 Tips

1. **Ranks are case-insensitive:** "general", "General", or "GENERAL" all work
2. **Plural recognized:** "generals" or "General" both work
3. **Natural language:** The AI tries to understand natural phrasing
4. **Be specific:** Include names and ranks clearly

---
```
/tf show all members
/tf list all commanders
/tf what rank is João?
/tf change Sarah to Marshal
/tf add Mike as Aspirant
/tf log raid for John
/tf remove Bob
```

All of these should work perfectly.
