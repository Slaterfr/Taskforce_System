# How to Get Roblox Role IDs for Rank Mapping

There are **3 ways** to see the role IDs you need to map:

## Method 1: Use the Rank Mappings Page (Easiest) ✅

1. **Make sure your `.env` file has `ROBLOX_GROUP_ID` set**
2. **Start your Flask app**
3. **Go to `/roblox/rank_mappings`** in your browser
4. **Look at the "Available Roblox Roles" table** at the top of the page
   - It shows all roles from your group
   - Each row shows: **Role Name** → **Role ID** → **Rank**
   - Copy the **Role ID** (the number) for each rank you want to map

**Example:**
```
Role Name: Aspirant    → Role ID: 123    → Rank: 1
Role Name: Novice      → Role ID: 124    → Rank: 2
Role Name: Marshal     → Role ID: 130    → Rank: 9
```

Then when creating a mapping:
- **System Rank**: `Aspirant`
- **Roblox Role ID**: `123`
- **Roblox Role Name**: `Aspirant` (optional, but helpful)

## Method 2: Use Roblox API Directly

If the page doesn't show roles (group ID not set), you can use the API:

1. **Get your group ID** from your Roblox group URL
2. **Open this URL in your browser:**
   ```
   https://groups.roblox.com/v1/groups/{YOUR_GROUP_ID}/roles
   ```
   Replace `{YOUR_GROUP_ID}` with your actual group ID

3. **You'll see JSON like this:**
   ```json
   {
     "roles": [
       {
         "id": 123,
         "name": "Aspirant",
         "rank": 1
       },
       {
         "id": 124,
         "name": "Novice",
         "rank": 2
       }
     ]
   }
   ```

4. **The `id` field is what you need** for the Role ID

## Method 3: Check Roblox Group Settings

1. **Go to your Roblox group page**
2. **Click "Configure Group"** (if you have permissions)
3. **Go to "Roles" tab**
4. **Look at each role** - the Role ID might be visible in the URL or page source
   - Or use browser DevTools (F12) → Network tab → Look for API calls

## Quick Reference

Once you have the role IDs, create mappings like this:

| System Rank | Roblox Role ID | Roblox Role Name |
|------------|---------------|------------------|
| Aspirant    | 123           | Aspirant         |
| Novice      | 124           | Novice           |
| Adept       | 125           | Adept            |
| Crusader    | 126           | Crusader         |
| Paladin     | 127           | Paladin          |
| Exemplar    | 128           | Exemplar         |
| Prospect    | 129           | Prospect         |
| Commander   | 130           | Commander        |
| Marshal     | 131           | Marshal          |
| General     | 132           | General          |
| Chief General | 133         | Chief General    |

**Note:** Your actual Role IDs will be different! Use Method 1 or 2 to get the real values.

## Troubleshooting

### "No roles loaded" on the page?
- Check that `ROBLOX_GROUP_ID` is set in your `.env` file
- Make sure the group ID is correct
- The group must be accessible (public or you're logged in)

### Can't see roles in Roblox group settings?
- You need to be a group owner/admin to see role management
- Or use Method 2 (API) - it works for public groups

### Role IDs don't match?
- Make sure you're looking at the correct group
- Role IDs are unique to each group
- Double-check the group ID in your `.env` file

