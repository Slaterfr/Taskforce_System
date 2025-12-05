"""
Generate secure API key for Discord bot integration
"""
import secrets

# Generate a secure random API key
api_key = secrets.token_urlsafe(32)

print("=" * 70)
print("DISCORD BOT API KEY GENERATED")
print("=" * 70)
print()
print("Copy the following line to your .env file:")
print()
print(f"DISCORD_BOT_API_KEY={api_key}")
print()
print("Also add these optional configurations:")
print()
print("API_RATE_LIMIT=100")
print("API_ENABLE_LOGGING=true")
print("DISCORD_NOTIFICATION_WEBHOOK_URL=your-webhook-url-here")
print()
print("=" * 70)
print("IMPORTANT: Keep this key secret! Never commit it to git.")
print("=" * 70)
