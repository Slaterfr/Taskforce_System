# � Taskforce Management System - User Manual

**Version**: 2.0.0  
**Last Updated**: March 2026

---

## 📑 Quick Navigation

- [What is This System?](#what-is-this-system)
- [How Do I Log In?](#how-do-i-log-in)
- [Checking Your Points](#checking-your-points)
- [Viewing The Roster](#viewing-the-roster)
- [Staff: Managing Members](#staff-managing-members)
- [Staff: Logging Activities](#staff-logging-activities)
- [Using The Discord Bot](#using-the-discord-bot)
- [Understanding Ranks & Rewards](#understanding-ranks--rewards)
- [Need Help?](#need-help)

---

## ❓ What is This System?

The **Taskforce Management System** is an all-in-one tool for managing your Roblox group. Here's what it does:

### 📊 Activity Tracking
Every two weeks, we run "Activity Check" (AC) periods. Members need to participate in activities (like training, raids, patrols) to earn points. This system tracks all of that automatically.

### 🎖️ Rank Management
Keep your member rankings organized. When someone gets promoted or demoted, the system automatically syncs it to the Roblox group.

### 💬 Discord Integration
Ask the Discord bot to check points, log activities, or manage members without leaving Discord.

### 📈 Real-Time Updates
Get instant notifications when activities are logged or ranks change. Always know what's happening in your group.

### 👥 Member Roster
View all members, their ranks, and activity history in one place.

---

## 🔐 How Do I Log In?

### Public Users (View-Only Access)

You can view the roster and AC progress **without logging in**. Just visit the website!

```
[SCREENSHOT PLACEHOLDER: Landing page with public roster view]
```

### Staff Members (Full Access)

Staff need to log in to access the management dashboard.

**Steps:**
1. Go to the website
2. Click **"Staff Login"** button
3. Enter the staff password
4. Click **"Login"**

```
[SCREENSHOT PLACEHOLDER: Staff login page with password field]
```

You're now in the **Dashboard**! Here you can manage members and activities.

---

## ✅ Activity Check (AC) - What You Need to Know

### What is an Activity Check?

Every **two weeks**, we have an "Activity Check" period. During this time, members need to participate in activities (training, raids, patrols, missions, etc.) to earn **points**.

Each member has a **quota** - a minimum number of points they need to earn. If they reach their quota, they pass the AC!

**Example:**
- Sarah is a Commander
- Her quota is **2.0 points**
- She logs:
  - 1 Training (1.0 pt) ✓
  - 1 Raid (1.5 pts) ✓
- Her total: **2.5 points** → **PASSED!** (quota was 2.0)

```
[SCREENSHOT PLACEHOLDER: AC dashboard showing current period and quota progress]
```

### Understanding Ranks & Quotas

Each rank has a different point quota:

| Your Rank | Points Needed |
|-----------|---------------|
| Prospect | 1.0 pt |
| Commander | 2.0 pts |
| Marshal | 3.0 pts |
| General | 3.0 pts |
| Chief General | 3.0 pts |

**Lower ranks have lower quotas.** This makes it easier for newer members to stay active.

---

## 🎯 Checking Your Points

### How to Check Your Points (Discord Bot)

You can ask the Discord bot to check your points:

**Type this in Discord:**
```
@bot how many points do I have
```

**The bot responds with:**
```
📊 AC Points: your_username
Current Points: 2.5
Quota Required: 3.0
Progress: 83.3%
Status: ██████░░░░ 
⏳ 0.5 more points needed
```

```
[SCREENSHOT PLACEHOLDER: Discord bot response showing points and progress bar]
```

### How to Check Your Points (Website)

1. Visit the website
2. Go to **"AC Progress"** section (no login needed)
3. Find your name in the list
4. Your current points and quota will be displayed

```
[SCREENSHOT PLACEHOLDER: AC progress list on website showing all members' points]
```

---

## 📋 Viewing The Roster

### See All Members

**On the Website:**
1. Click **"Roster"** or go to the home page
2. You'll see all active members listed with their ranks

```
[SCREENSHOT PLACEHOLDER: Member roster page with search and filters]
```

**Can you do on the Roster page:**
- 🔍 **Search** by member name
- 🏷️ **Filter** by rank
- 👤 **Click a member** to see their activity history

---

## 👔 Staff: Managing Members

### Only staff members can do these things!

You need to **log in with the staff password** first.

#### Add a New Member

**Steps:**
1. Click **"Dashboard"** (after logging in)
2. Click **"Add Member"** button
3. Fill in the form:
   - Discord username (required)
   - Roblox username (optional)
   - Starting rank (defaults to Prospect)
4. Click **"Add Member"**

```
[SCREENSHOT PLACEHOLDER: Add member form]
```

**Example:**
- Discord Username: `john_doe`
- Roblox Username: `john_roblox_123`
- Rank: `Prospect`

#### Edit Member Details

**Steps:**
1. Go to **"Dashboard"**
2. Find the member in the list
3. Click **"Edit"** button
4. Update any information
5. Click **"Save"**

```
[SCREENSHOT PLACEHOLDER: Edit member form]
```

#### Remove a Member

**Steps:**
1. Go to **"Dashboard"**
2. Find the member
3. Click **"Remove"** button
4. Confirm deletion

⚠️ **Note:** This will delete all their activity history! Use carefully.

```
[SCREENSHOT PLACEHOLDER: Confirm removal dialog]
```

#### Promote or Demote a Member

**Steps:**
1. Go to **"Dashboard"**
2. Find the member
3. Click **"Change Rank"**
4. Select the new rank
5. Click **"Promote"** or **"Demote"**

```
[SCREENSHOT PLACEHOLDER: Rank change dialog]
```

**What happens:**
- Their rank changes in the system
- Automatically synced to the Roblox group (if enabled)
- Discord gets a notification
- Change is logged in history

---

## 🎮 Staff: Logging Activities

This is how members earn points during the AC period!

### What Activities Can You Log?

| Activity | Points | Notes |
|----------|--------|-------|
| **Raid** | 1.5 | Counts toward "Most Events" title |
| **Patrol** | 1.5 | Counts toward "Most Events" title |
| **Training** | 1.0 | |
| **Mission** | 0.5 | |
| **Tryout** | 1.5 | Recruitment activity |
| **Evaluation** | 0.5 | Only 1 per AC period |
| **Supervision** | 1.0 | |
| **Cancelled Training** | 0.5 | Only 1 per AC period |
| **Cancelled Tryout** | 0.5 | Only 1 per AC period |

### Quick Log (Fastest Way)

**Steps:**
1. Log in to staff dashboard
2. Click **"AC Dashboard"**
3. Click **"Quick Log"**
4. Select member from dropdown
5. Select activity type
6. Enter quantity (how many)
7. Click **"Log"**

```
[SCREENSHOT PLACEHOLDER: Quick log interface]
```

**What happens next:**
- Member instantly gets the points
- A confirmation message appears: `✅ Logged Training (1.0 pts) for **john_doe**, they now have 2.5/3.0 points.`
- Discord notification is sent
- Their quota progress updates

### Full Activity Log (More Details)

**Steps:**
1. Go to **"AC Dashboard"**
2. Click **"Log Activity"** button
3. Fill in the form:
   - Member (required)
   - Activity type (required)
   - Quantity (default 1)
   - Description (optional - what they did)
   - Date (optional - when they did it)
4. Click **"Log Activities"**

```
[SCREENSHOT PLACEHOLDER: Full activity logging form]
```

**Example:**
- Member: sarah_username
- Activity: Raid
- Quantity: 1
- Description: "Led the Friday night raid"
- Date: 2026-03-14

### Undo a Logged Activity

Made a mistake? You can remove it!

**Steps:**
1. Go to **"AC Dashboard"**
2. Find the activity in the list
3. Click **"Remove"** or **"Undo"**
4. Confirm

```
[SCREENSHOT PLACEHOLDER: Activity list with remove button]
```

**What happens:**
- Activity is deleted
- Member's points go down
- Discord notification is sent
- Everyone knows what was removed

---

## 💬 Using The Discord Bot

The Discord bot lets you manage everything without leaving Discord!

### Available Commands

#### Check Points
```
@bot how many points do I have
@bot check points for john_doe
@bot what are sarah's points
```

**Response:** Shows current points, quota, and progress bar

```
[SCREENSHOT PLACEHOLDER: Discord bot points response]
```

#### Log an Activity
```
@bot log training for john_doe
@bot log 3 raids for sarah
@bot log cancelled tryout for bob
```

**Response:** Confirms activity logged with updated quota

```
[SCREENSHOT PLACEHOLDER: Discord bot activity confirmation]
```

#### Remove an Activity
```
@bot remove training for john_doe
@bot undo patrol for sarah
```

**Response:** Confirms activity removed with updated quota

#### Change a Rank
```
@bot change john to commander
@bot promote sarah to general
```

**Response:** Confirms rank change

#### View Member Info
```
@bot what rank is john_doe
@bot get info for sarah
```

**Response:** Shows member details

#### List Members
```
@bot show all members
@bot show all generals
@bot list all commanders
```

**Response:** Embed with members grouped by rank

#### Add New Member
```
@bot add new member john_doe with roblox name john_roblox
```

#### Remove Member
```
@bot remove john_doe from system
```

### How Does The Bot Understand Me?

The bot uses **AI to understand natural language**. You can phrase commands multiple ways:

```
All of these work the same:
✅ @bot log training for john
✅ @bot add training for john
✅ @bot john did training
✅ @bot log john training
```

Just be clear about:
- Who (member name)
- What (activity or action)
- How much (if applicable - number of activities)

```
[SCREENSHOT PLACEHOLDER: Discord bot command examples]
```

---

## 🏆 Understanding Ranks & Rewards
### Member Ranks

Members progress through ranks as they become more active:

**Regular Members:**
- Aspirant
- Novice
- Adept
- Crusader
- Paladin
- Exemplar

**Staff Ranks** (Special permissions):
- Prospect
- Commander
- Marshal
- General
- Chief General

### 🎖️ Understanding Titles & Rewards

Members can earn special titles. Here's how the new system works:

#### Two Types of Titles

**⏱️ HWTM - Host with the Most (Awarded Every Period)**
- **When:** End of every 2-week AC period
- **Based on:** Events in **that single period only** (Training + Raid + Patrol)
- **Requirement:** 5+ events in the period
- **Winner:** Member with the most events in that period
- **Example:** Sarah had 6 events in Period 1 → Gets HWTM at end of Period 1

**📅 Monthly Titles (Awarded Only at Month End)**

Every 2 periods = 1 month. At the end of the month, stats from ALL periods in that month are combined to award:

- **⚔️ Leggionary**
  - Based on: **Total Raids + Patrols across the entire month**
  - Requirement: 5+ combined Raids and Patrols
  - Winner: Member with most Raid + Patrol events
  - Example: Sarah had 2 Raids (Period 1) + 3 Raids (Period 2) + 4 Patrols (combined) = 9 total → Wins Leggionary

- **🔍 Scout**
  - Based on: **Total Tryouts across the entire month**
  - Requirement: 5+ tryouts
  - Winner: Member who conducted most tryouts across all periods

- **📖 Taskmaster**
  - Based on: **Total Missions across the entire month**
  - Requirement: 5+ missions
  - Winner: Member who posted most missions across all periods

#### How the Monthly Cycle Works

```
PERIOD 1 (Week 1-2)
    ↓
Collect stats → Award HWTM → Store in history
    ↓
PERIOD 2 (Week 3-4)
    ↓
Collect stats → Award HWTM → Store in history
    ↓
FINALIZE PERIOD 2 (End of Month)
    ↓
Sum stats from Period 1 + Period 2
    ↓
Award Leggionary, Scout, Taskmaster
    ↓
PERIOD 3 (Week 5-6) [Start of New Month]
    ↓
HWTM counter resets, other titles reset → Cycle repeats
```

#### Real Example Timeline

```
MARCH 1-14 (Period 1)
John:  3 Raids, 1 Patrol, 2 Training = 6 events
Sarah: 2 Raids, 2 Patrols, 1 Training = 5 events
End: HWTM → John (6 events) ⭐

MARCH 15-28 (Period 2)
John:  1 Raid, 2 Patrols, 2 Training = 5 events
Sarah: 3 Raids, 3 Patrols, 1 Training = 7 events
End: HWTM → Sarah (7 events) ⭐

MARCH 28 (Month End - Finalize Period 2)
Calculate Monthly Totals:
- Leggionary: Sarah (2+3=5 Raids) + (2+3=5 Patrols) = 10 events ⭐
- Scout: Nobody (no one had 5+ tryouts)
- Taskmaster: Nobody (no one had 5+ missions)

APRIL 1-14 (Period 3 - New Month)
Stats reset, start fresh cycle...
```

```
[SCREENSHOT PLACEHOLDER: Titles and rewards announcement showing both period and monthly awards]
```

---

## 🎓 Activity Check Period Workflow

Here's what happens during each AC period:

```
📅 AC Period Timeline

PERIOD 1 (Week 1-2)
    ↓
Members Log Activities
    ↓
Check Progress Anytime (website/Discord bot)
    ↓
End of Period 1
    ↓
Calculate HWTM → Award if qualifies ⭐
    ↓
Store stats for monthly calculation

PERIOD 2 (Week 3-4)
    ↓
Members Log Activities
    ↓
Check Progress Anytime (website/Discord bot)
    ↓
End of Period 2
    ↓
Calculate HWTM → Award if qualifies ⭐
    ↓
FINALIZE PERIOD 2 (Staff Action)
    ↓
Capture all stats → Calculate Monthly Winners
    ↓
Award Monthly Titles: Leggionary, Scout, Taskmaster ⭐
    ↓
PERIOD 3 BEGINS (New Month)
    ↓
Stats reset, cycle repeats...
```
```

```
[SCREENSHOT PLACEHOLDER: AC period timeline]
```

---

## 📊 Viewing Your AC Progress

### On the Website

1. Go to home page
2. Click **"AC Progress"** or **"View Progress"**
3. Find your name in the list
4. You'll see:
   - Current points earned
   - Your quota requirement
   - Percentage complete (%)
   - Progress bar
   - Current AC period dates

```
[SCREENSHOT PLACEHOLDER: AC progress page showing all members]
```

### In Discord

Ask the bot:
```
@bot how many points do I have
```

The bot shows you visually with a progress bar! ██████░░░░

```
[SCREENSHOT PLACEHOLDER: Discord bot points response with progress bar]
```

---

## 🔄 Inactivity Notices (IA)

If you're going to be **away or unable to participate**, you can request an **Inactivity Notice (IA)**.

**What does IA do?**
- Protects you from AC requirements during your absence
- You won't be penalized for missing activities
- Staff approves the notice

**How to request IA:**
1. Contact your staff leader
2. Tell them your absence dates
3. Staff approves and logs it in the system

```
[SCREENSHOT PLACEHOLDER: Inactivity notice form]
```

---

## 💾 Exporting Reports

Staff can export activity data for records.

**Steps:**
1. Log in to dashboard
2. Go to **"AC Dashboard"**
3. Click **"Export to Excel"**
4. Select the AC period
5. Click **"Download"**

```
[SCREENSHOT PLACEHOLDER: Export report dialog]
```

**What you get:**
- All members and their activities
- Points earned
- Title awards
- In Excel format for sharing/presenting

---

## 🔗 Roblox Group Sync

If your system is **connected to your Roblox group**, ranks automatically sync!

**How it works:**
1. Staff changes member rank in system
2. System updates the Roblox group rank automatically
3. Discord notification sent
4. In-game rank changes instantly

```
[SCREENSHOT PLACEHOLDER: Rank change with Roblox sync confirmation]
```

**This means:**
✅ No manually updating Roblox ranks - it's automatic!
✅ Keeps system and Roblox in-sync
✅ Instant updates for promoted members

---

## 🆘 Need Help?

### Common Questions

**Q: What if I logged the wrong activity?**
A: Staff can remove it anytime! Just ask them to undo it.

**Q: How do I check if I passed the AC?**
A: Look at your points vs quota. If points ≥ quota, you passed!

**Q: Can I log activities for past dates?**
A: Yes! Staff can set any date when logging activities.

**Q: What if I was inactive?**
A: Request an Inactivity Notice from staff. They'll log it.

**Q: How does the bot understand my commands?**
A: It uses AI! Just mention the member, activity, and action naturally.

**Q: Where do I see my activity history?**
A: Click your name on the Roster page, or ask staff.

### Something Not Working?

**Bot not responding?**
- Make sure you're using `@bot` correctly
- Check bot is online in Discord
- Try a simpler command first

**Can't see my points?**
- Visit the "AC Progress" page
- Make sure the AC period is active
- Contact staff if you don't see yourself listed

**Confused about ranks?**
- See the "Understanding Ranks & Rewards" section above
- Ask staff for clarification

**Need to contact staff?**
- In Discord: Mention your staff role
- In-game: Talk to a staff member
- Via website: Check the contact information

---

## 📌 Quick Reference Card

### Website Pages

| Page | What You See | Login Needed? |
|------|-------------|--------------|
| **Home / Roster** | All members & ranks | No |
| **AC Progress** | Everyone's points &quota | No |
| **Member Profile** | Activity history | No |
| **Dashboard** | Management tools | Yes (Staff) |
| **Quick Log** | Fast activity logging | Yes (Staff) |
| **Statistics** | Activity summaries | Yes (Staff) |

### Discord Bot Commands

| What You Want | Type This |
|---------------|-----------|
| Check your points | `@bot how many points do I have` |
| Check someone's points | `@bot points for john_doe` |
| Log an activity | `@bot log training for john` |
| Remove activity | `@bot remove training for john` |
| Change rank | `@bot change john to commander` |
| View member info | `@bot info on john` |
| List members | `@bot show all members` |

### Activity Quick Sheet

| Activity | Points | Best For |
|----------|--------|----------|
| Raid | 1.5 pts | Major events |
| Patrol | 1.5 pts | Group patrols |
| Training | 1.0 pt | Teaching |
| Mission | 0.5 pts | Secondary activities |
| Tryout | 1.5 pts | Recruitment |

### Quotas by Rank

| Rank | Points Needed | Time Period |
|------|--------------|-----------|
| Prospect | 1.0 | 2 weeks |
| Commander | 2.0 | 2 weeks |
| Marshal/General | 3.0 | 2 weeks |

---

## 📞 Contact & Support

**Need help?**
- Ask in Discord
- Talk to your staff lead
- Visit the system home page

**Report a bug?**
- Tell a staff member
- Include: What you were doing, what went wrong, when it happened

**Have a suggestion?**
- Share it with leadership
- We're always improving!

---

## 📝 Version History

### v2.0.0 (Current - March 2026)
✅ Members can check their own points
✅ Ability to remove/undo activities
✅ Mobile-friendly design - works on phones!
✅ Better Discord notifications
✅ Updated activity point values

### v1.5.0 (January 2026)
✅ Discord bot AI commands added
✅ Real-time activity logging
✅ Automatic quota progress tracking

### v1.0.0 (November 2025)
✅ System launched!
✅ Basic member management
✅ Activity Check system
✅ Roblox rank syncing

---

**Last Updated**: March 14, 2026  
**System Status**: ✅ Live and Running  
**Need Help?** Contact your staff!

