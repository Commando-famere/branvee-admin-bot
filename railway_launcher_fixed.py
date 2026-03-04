"""
Fixed Railway Launcher - Runs bots sequentially with different tokens
"""
import subprocess
import sys
import os

if __name__ == '__main__':
    print("="*60)
    print("🚀 BRANVEE BOTS LAUNCHER")
    print("="*60)
    
    # Get tokens from environment
    admin_token = os.environ.get('ADMIN_BOT_TOKEN')
    signal_token = os.environ.get('SIGNAL_BOT_TOKEN')
    
    print(f"✅ Admin Bot token: {admin_token[:10]}...")
    print(f"✅ Signal Bot token: {signal_token[:10]}...")
    
    # Run admin bot in background
    admin_process = subprocess.Popen(
        ["python", "railway_admin_bot.py"],
        env={**os.environ, "BOT_TOKEN": admin_token}
    )
    print("✅ Admin Bot started")
    
    # Run signal bot in background
    signal_process = subprocess.Popen(
        ["python", "railway_signal_bot.py"],
        env={**os.environ, "BOT_TOKEN": signal_token}
    )
    print("✅ Signal Bot started")
    
    print("\n📊 Both bots running...")
    print("="*60)
    
    try:
        admin_process.wait()
        signal_process.wait()
    except KeyboardInterrupt:
        admin_process.terminate()
        signal_process.terminate()
        print("\n⏹️  Bots stopped")
