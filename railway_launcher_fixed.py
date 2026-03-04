"""
Fixed Railway Launcher - Runs bots sequentially with different tokens
"""
import subprocess
import sys
import os
import time

if __name__ == '__main__':
    print("="*60)
    print("🚀 BRANVEE BOTS LAUNCHER")
    print("="*60)
    
    # Get tokens from environment with error handling
    admin_token = os.environ.get('ADMIN_BOT_TOKEN')
    signal_token = os.environ.get('SIGNAL_BOT_TOKEN')
    
    if not admin_token:
        print("❌ ADMIN_BOT_TOKEN not set in environment!")
        print("Please set it in Railway dashboard:")
        print("  ADMIN_BOT_TOKEN = 8659878049:AAFosBtLo5ElKjH3w3pcfxvM19SOT-DwQ7I")
        sys.exit(1)
    
    if not signal_token:
        print("❌ SIGNAL_BOT_TOKEN not set in environment!")
        print("Please set it in Railway dashboard:")
        print("  SIGNAL_BOT_TOKEN = 8741454658:AAGlyxcVQMH7tKd13OmM2Y2VGa9ex9LbPfo")
        sys.exit(1)
    
    print(f"✅ Admin Bot token: {admin_token[:10]}...")
    print(f"✅ Signal Bot token: {signal_token[:10]}...")
    
    # Run admin bot in background
    try:
        admin_process = subprocess.Popen(
            ["python", "railway_admin_bot.py"],
            env={**os.environ, "BOT_TOKEN": admin_token}
        )
        print(f"✅ Admin Bot started (PID: {admin_process.pid})")
    except Exception as e:
        print(f"❌ Failed to start Admin Bot: {e}")
    
    time.sleep(2)  # Give admin bot time to start
    
    # Run signal bot in background
    try:
        signal_process = subprocess.Popen(
            ["python", "railway_signal_bot.py"],
            env={**os.environ, "BOT_TOKEN": signal_token}
        )
        print(f"✅ Signal Bot started (PID: {signal_process.pid})")
    except Exception as e:
        print(f"❌ Failed to start Signal Bot: {e}")
    
    print("\n📊 Both bots are running...")
    print("="*60)
    
    try:
        admin_process.wait()
        signal_process.wait()
    except KeyboardInterrupt:
        admin_process.terminate()
        signal_process.terminate()
        print("\n⏹️  Bots stopped")
    except Exception as e:
        print(f"Error: {e}")
