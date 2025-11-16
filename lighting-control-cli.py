import asyncio
import aiohttp
import time
from collections import deque
from statistics import mean
import sys
import tty
import termios

BASE_URL = "http://localhost:3000"
DEVICE_ID = "C82E4761852A"
TEMPO = 120  # Global tempo variable
COLORS = ["#FE00AE", "#00FFDD"]  # Global colour sequence initially [magenta, cyan]

# Color palette
NAMED_COLORS = {
    "white": "#ffffff",
    "red": "#FF0000",
    "orange": "#FF2000",
    "yellow": "#FF9200",
    "ferngreen": "#AAFF00",
    "green": "#00FF00",
    "seagreen": "#0EFF1E",
    "cyan": "#00FFDD",
    "lavender": "#4433fa",
    "blue": "#0000FF",
    "violet": "#9900FF",
    "magenta": "#FE00AE",
    "pink": "#FF0016"
}

endpoints = {
    "get_devices": "/api/devices",
    "get_state": "/api/device/",
    "set_colour": "/api/color",
    "set_power": "/api/power",
    "set_effect": "/api/effect"
}

# All supported effect names
effects = [
    "seven_color_cross_fade",
    "red_gradual_change",
    "green_gradual_change",
    "blue_gradual_change",
    "yellow_gradual_change",
    "cyan_gradual_change",
    "purple_gradual_change",
    "white_gradual_change",
    "red_green_cross_fade",
    "red_blue_cross_fade",
    "green_blue_cross_fade",
    "seven_color_strobe_flash",
    "red_strobe_flash",
    "green_strobe_flash",
    "blue_stobe_flash",
    "yellow_strobe_flash",
    "cyan_strobe_flash",
    "purple_strobe_flash",
    "white_strobe_flash",
    "seven_color_jumping"
]

session = None
latency_history = deque(maxlen=50)  # Track recent latencies

def resolve_color(color_input):
    if color_input.startswith("#"):
        return color_input
    return NAMED_COLORS.get(color_input.lower(), color_input)

async def get_session():
    global session
    if session is None:
        connector = aiohttp.TCPConnector(
            limit=10,
            ttl_dns_cache=300,
            keepalive_timeout=30
        )
        timeout = aiohttp.ClientTimeout(total=1.0)
        session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    return session

async def close_session():
    global session
    if session:
        await session.close()
        session = None

async def api_call(method, endpoint, data=None):
    url = BASE_URL + endpoint
    sess = await get_session()
    start = time.perf_counter()
    
    try:
        if method == "GET":
            async with sess.get(url) as resp:
                text = await resp.text()
        else:  # POST
            async with sess.post(url, json=data) as resp:
                text = await resp.text()
        
        latency = time.perf_counter() - start
        latency_history.append(latency)
        return text
    except asyncio.TimeoutError:
        print(f"Timeout on {endpoint}")
        return None

async def get_devices():
    return await api_call("GET", endpoints["get_devices"])

async def get_device_state(device):
    return await api_call("GET", endpoints["get_state"] + device)

async def set_color(color, brightness):
    data = {"id": DEVICE_ID, "color": color, "brightness": brightness}
    result = await api_call("POST", endpoints["set_colour"], data)
    return result == "OK"

async def set_power(power):
    data = {"id": DEVICE_ID, "power": power}
    result = await api_call("POST", endpoints["set_power"], data)
    return result == "OK"

async def set_effect(effect, speed):
    data = {"id": DEVICE_ID, "effect": effect, "speed": speed}
    result = await api_call("POST", endpoints["set_effect"], data)
    return result == "OK"

async def flash_simple():
    asyncio.create_task(set_effect("white_strobe_flash", 1))
    await asyncio.sleep(0.05)
    asyncio.create_task(set_power(False))

# Class for scheduled timing loops
class ScheduledLoop:
    def __init__(self, beats_per_cycle=2, intervalOverride=None):
        self.beats_per_cycle = beats_per_cycle
        self.start_time = None
        self.cycle_num = 0
        self.current_tempo = TEMPO
        self.interval = intervalOverride
    
    def calculate_interval(self):
        # Calculate interval based on current tempo
        beat_duration = 60 / TEMPO
        if self.interval:
            return self.interval
        return beat_duration * self.beats_per_cycle
    
    def reset_timing(self):
        # Reset timing to current moment
        self.start_time = time.perf_counter()
        self.cycle_num = 0
    
    async def wait_for_next_cycle(self):
        # Wait until the next scheduled cycle, with drift handling
        if self.start_time is None:
            self.reset_timing()
        
        interval = self.calculate_interval()
        scheduled_time = self.start_time + (self.cycle_num * interval)
        now = time.perf_counter()
        
        wait_time = scheduled_time - now
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        elif wait_time < -0.1:  # More than 100ms behind
            print(f"   Resync: {-wait_time*1000:.1f}ms behind")
            self.reset_timing()
            return False  # Signal to skip this cycle
        
        self.cycle_num += 1
        return True
    
    def check_tempo_changed(self):
        # Check if tempo has changed and reset if needed
        if TEMPO != self.current_tempo:
            self.current_tempo = TEMPO
            self.reset_timing()
            interval = self.calculate_interval()
            print(f"Tempo changed to {TEMPO} BPM, interval: {interval*1000:.1f}ms")
            return True
        return False

async def color_cycle_loop(mode="fade", color=None):
    # Determine colors to use
    if color is None:
        colors_to_use = COLORS.copy()
        print(f"Using color list: {colors_to_use}")
    else:
        colors_to_use = [color]
    color_index = 0
    current_color = colors_to_use[color_index]
    
    loop = ScheduledLoop(beats_per_cycle=2)
    interval = loop.calculate_interval()
    
    print(f"Starting {mode} loop: {TEMPO} BPM ({mode} every 2 beats)")
    print(f"Interval: {interval*1000:.1f}ms")
    
    # Set initial state
    await set_color(current_color, 100)
    if mode == "fade":
        pass
        # Warmup for fade mode
        # for _ in range(2):
        #     await set_power(True)
        #     await asyncio.sleep(0.01)
        # power_state = True
    else:
        await set_power(True)
    
    while True:
        loop.check_tempo_changed()
        
        # Check if colors changed
        if color is None and colors_to_use != COLORS:
            colors_to_use = COLORS.copy()
            print(f"Colors updated: {colors_to_use}")
        
        # Wait for next cycle
        if not await loop.wait_for_next_cycle():
            continue
        
        if mode == "fade":
            # Toggle power for fade
            power_state = not power_state
            asyncio.create_task(set_power(power_state))
            
            # Change color when powering on
            if power_state and len(colors_to_use) > 1:
                color_index = (color_index + 1) % len(colors_to_use)
                current_color = colors_to_use[color_index]
                asyncio.create_task(set_color(current_color, 100))
                # print(f"Color: {current_color}")
        else:  # "switch" mode
            # Change to next Colour without fading
            if len(colors_to_use) > 1:
                color_index = (color_index + 1) % len(colors_to_use)
                current_color = colors_to_use[color_index]
            
            asyncio.create_task(set_color(current_color, 100))
            # print(f"Color: {current_color}")

async def strobe_loop(color):
    # TODO: Handle strobe colour using list of possible effects
    if color is None:
        effect_color = "white_strobe_flash"
    else:
        effect_color = "white_strobe_flash"
        # match color:
        #   case "white":
    """
    "seven_color_strobe_flash",
    "red_strobe_flash",
    "green_strobe_flash",
    "blue_stobe_flash",
    "yellow_strobe_flash",
    "cyan_strobe_flash",
    "purple_strobe_flash",
    """

    # Do not want to base strobe frequency on BPM so override loop interval
    # 0.08s interval = 80ms (period) = 12.5Hz?
    loop = ScheduledLoop(beats_per_cycle=None, intervalOverride=0.08)
    interval = loop.calculate_interval()

    print(f"Starting strobe loop: {TEMPO} BPM")
    print(f"Interval: {interval*1000:.1f}ms")

    # Warmup
    # for _ in range(3):
    #     await set_power(True)
    #     await asyncio.sleep(0.05)

    while True:
        if not await loop.wait_for_next_cycle():
            continue

        asyncio.create_task(set_effect("white_strobe_flash", 50))
        # asyncio.create_task(set_power(False))

async def beat_loop():
    # flash every beat
    loop = ScheduledLoop(beats_per_cycle=1)
    interval = loop.calculate_interval()
    
    print(f"Starting beat loop: {TEMPO} BPM")
    print(f"Beat interval: {interval*1000:.1f}ms")
    
    # Warmup
    for _ in range(3):
        await set_power(True)
        await asyncio.sleep(0.05)
    
    while True:
        loop.check_tempo_changed()
        
        if not await loop.wait_for_next_cycle():
            continue
        
        # Fire the beat
        asyncio.create_task(set_effect("white_strobe_flash", 100))
        # asyncio.create_task(set_power(False))

async def tap_tempo():
    global TEMPO
    tap_times = deque(maxlen=8)
    
    print("\n--- Tap Tempo Mode ---")
    print("Press 't' repeatedly to tap the beat")
    print("Press any other key to exit tap mode")
    print("Tap at least 2 times to calculate tempo\n")
    
    loop = asyncio.get_event_loop()
    
    old_settings = termios.tcgetattr(sys.stdin)
    
    try:
        tty.setcbreak(sys.stdin.fileno())
        
        while True:
            char = await loop.run_in_executor(None, sys.stdin.read, 1)
            
            if char.lower() == 't':
                now = time.perf_counter()
                tap_times.append(now)
                
                if len(tap_times) >= 2:
                    intervals = [tap_times[i] - tap_times[i-1] for i in range(1, len(tap_times))]
                    avg_interval = mean(intervals)
                    new_tempo = round(60 / avg_interval)
                    new_tempo = max(40, min(240, new_tempo))
                    
                    TEMPO = new_tempo
                    print(f"\r- Tempo: {TEMPO} BPM (from {len(tap_times)} taps)" + " " * 20)
                else:
                    print(f"\rTap {len(tap_times)}/2... (tap more)" + " " * 20, end="")
            else:
                print(f"\n\nExited tempo tapper. Final tempo: {TEMPO} BPM")
                break
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

def get_latency_stats():
    if not latency_history:
        return "No latency data yet"
    
    avg = sum(latency_history) / len(latency_history)
    min_lat = min(latency_history)
    max_lat = max(latency_history)
    
    return f"Latency: avg={avg*1000:.1f}ms, min={min_lat*1000:.1f}ms, max={max_lat*1000:.1f}ms"

# TODO: make this accept [tasks] and end them all
def stop_all_tasks(beat_task, fade_task, switch_task, strobe_task):
    stopped = []
    if beat_task:
        beat_task.cancel()
        stopped.append("beat")
    if fade_task:
        fade_task.cancel()
        stopped.append("fade")
    if switch_task:
        switch_task.cancel()
        stopped.append("switch")
    if strobe_task:
        strobe_task.cancel()
        stopped.append("strobe")
    if stopped:
        print(f"Stopped: {', '.join(stopped)}")
    
    return None, None, None, None

async def interactive_mode():
    global TEMPO, COLORS
    
    i = 0
    power = False
    strobe = False
    beat_task = None
    fade_task = None
    switch_task = None
    strobe_task = None

    previous_tasks = [fade_task != None, switch_task != None]
    
    print("Commands:")
    print("  e - cycle effects")
    print("  p - toggle power")
    print("  #RRGGBB or color_name - set color (e.g., 'red', 'cyan', '#ff0000')")
    print("  s - toggle strobe on or off")
    print("  f - a single white flash")
    print("  ] - double the bpm")
    print("  [ - half the bpm")
    print("  colors [color1] [color2] ... - set color list (supports names or hex)")
    print("  fade [color] - fade effect every 2 beats")
    print("  switch [color] - instant color switch every 2 beats")
    print("  beat - beat loop (strobe flash)")
    print("  tap - tempo tapper")
    print("  tempo [bpm] - set tempo manually")
    print("  stop - stop beat/fade/switch loop")
    print("  stats - show latency stats")
    print("  palette - show available color names")
    print("  help - show help command (TODO)")
    print("  q - quit")
    print()
    print(f"Current tempo: {TEMPO} BPM")
    print(f"Current colors: {COLORS}")
    print()
    
    loop = asyncio.get_event_loop()
    
    while True:
        command = await loop.run_in_executor(None, input, "\n$: ")
        command = command.strip()
        
        if command == "q":
            break
        elif command == "e":
            asyncio.create_task(set_effect(effects[i % len(effects)], 100))
            i += 1
            print(f"Effect: {effects[(i-1) % len(effects)]}")
        elif command == "p":
            asyncio.create_task(set_power(power))
            power = not power
            print(f"Power: {'ON' if power else 'OFF'}")
        elif command.startswith("#") or command.lower() in NAMED_COLORS:
            color = resolve_color(command)
            asyncio.create_task(set_color(color, 100))
            print(f"Color set to: {color}")
        elif command == "f":
            # TODO: allow flash colours
            asyncio.create_task(flash_simple())
            print("Flash")
        elif command == "s":
            parts = command.split()
            color = resolve_color(parts[1]) if len(parts) > 1 else None
            # toggle
            strobe = not strobe
            if strobe:
                # save effect loop currently running, to restart when toggled off
                previous_tasks = [fade_task != None, switch_task != None]
            
            beat_task, fade_task, switch_task, strobe_task = stop_all_tasks(beat_task, fade_task, switch_task, strobe_task)
            if strobe:
                print("Strobe ON")
                strobe_task = asyncio.create_task(strobe_loop(color))
            else:
                print("Strobe OFF")
                if previous_tasks[0]:
                    fade_task = asyncio.create_task(color_cycle_loop("fade"))
                elif previous_tasks[1]:
                    switch_task = asyncio.create_task(color_cycle_loop("switch"))
            
        elif command.startswith("fade"):
            parts = command.split()
            color = resolve_color(parts[1]) if len(parts) > 1 else None
            beat_task, fade_task, switch_task, strobe_task = stop_all_tasks(beat_task, fade_task, switch_task, strobe_task)
            fade_task = asyncio.create_task(color_cycle_loop("fade", color))
        elif command.startswith("switch"):
            parts = command.split()
            color = resolve_color(parts[1]) if len(parts) > 1 else None
            beat_task, fade_task, switch_task, strobe_task = stop_all_tasks(beat_task, fade_task, switch_task, strobe_task)
            switch_task = asyncio.create_task(color_cycle_loop("switch", color))
        elif command.startswith("colors"):
            parts = command.split()
            if len(parts) > 1:
                new_colors = [resolve_color(c) for c in parts[1:]]
                new_colors = [c for c in new_colors if c.startswith("#")]
                if new_colors:
                    COLORS = new_colors
                    print(f"Colors set to: {COLORS}")
                else:
                    print("Invalid colors. Use color names or hex codes like: colors red green blue")
            else:
                print(f"Current colors: {COLORS}")
        elif command == "palette":
            print("\nAvailable color names:")
            for name, hex_code in sorted(NAMED_COLORS.items()):
                print(f"  {name:12} - {hex_code}")
            print()
        elif command == "beat":
            beat_task, fade_task, switch_task, strobe_task = stop_all_tasks(beat_task, fade_task, switch_task, strobe_task)
            beat_task = asyncio.create_task(beat_loop())
        elif command == "tap":
            await tap_tempo()
        elif command.startswith("tempo"):
            parts = command.split()
            if len(parts) > 1:
                try:
                    new_tempo = int(parts[1])
                    if 40 <= new_tempo <= 240:
                        TEMPO = new_tempo
                        print(f"Tempo set to {TEMPO} BPM")
                    else:
                        print("Tempo must be between 40 and 240 BPM")
                except ValueError:
                    print("Invalid tempo value")
            else:
                print(f"Current tempo: {TEMPO} BPM")
        elif command == "]":
            newTempo = TEMPO * 2
            TEMPO = newTempo
            print(f"New tempo: {TEMPO}")
        elif command == "[":
            newTempo = TEMPO / 2
            TEMPO = newTempo
            print(f"New tempo: {TEMPO}")
        elif command == "stop":
            beat_task, fade_task, switch_task, strobe_task = stop_all_tasks(beat_task, fade_task, switch_task, strobe_task)
            asyncio.create_task(set_power(False))
        elif command == "stats":
            print(get_latency_stats())
        # TODO: help - print help message
        else:
            print("Unknown command")

async def main():
    try:
        await interactive_mode()
    finally:
        await close_session()

if __name__ == "__main__":
    asyncio.run(main())