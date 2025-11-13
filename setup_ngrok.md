# ngrok Setup Instructions

## Step 1: Download ngrok
1. Go to https://ngrok.com/download
2. Download for Windows
3. Extract the `ngrok.exe` file

## Step 2: Sign up (Free)
1. Go to https://dashboard.ngrok.com/signup
2. Sign up for free account
3. Get your authtoken from the dashboard

## Step 3: Configure ngrok
1. Open PowerShell/CMD in the folder where `ngrok.exe` is
2. Run: `ngrok config add-authtoken YOUR_TOKEN_HERE`
   (Replace YOUR_TOKEN_HERE with your actual token)

## Step 4: Run Your App
1. In one terminal:
   ```bash
   cd Taskforce_System
   python app.py
   ```

2. In another terminal (where ngrok.exe is):
   ```bash
   ngrok http 5000
   ```

## Step 5: Share the URL
- ngrok will show a URL like: `https://abc123.ngrok-free.app`
- Share this with your teammates
- They can access it from anywhere!

## Tips:
- Free tier: URL changes each time you restart ngrok
- Free tier: Shows a warning page (teammates click "Visit Site" to continue)
- For fixed URL: Upgrade to paid plan or use Railway instead

