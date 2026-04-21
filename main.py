from machine import Pin, I2C, ADC, PWM
import ssd1306, time, assets, framebuf

# --- হার্ডওয়্যার সেটআপ ---
i2c_oled = I2C(0, scl=Pin(5), sda=Pin(4))
i2c_ina = I2C(1, scl=Pin(3), sda=Pin(2)) 
next_btn = Pin(14, Pin.IN, Pin.PULL_UP)
select_btn = Pin(15, Pin.IN, Pin.PULL_UP)
buzzer = PWM(Pin(17)) 
res_adc = ADC(26) 
led_probe = Pin(16, Pin.OUT)

oled = ssd1306.SSD1306_I2C(128, 64, i2c_oled)
def check_button_type(btn):
    """
    বাটনটি কতক্ষণ চেপে ধরা হয়েছে তা চেক করে।
    ০ = কোনো প্রেস নেই, ১ = শর্ট প্রেস, ২ = লং প্রেস (১ সেকেন্ডের বেশি)
    """
    if btn.value() == 0:
        t_start = time.ticks_ms()
        while btn.value() == 0: # যতক্ষণ চেপে ধরে আছিস
            time.sleep(0.01)
        duration = time.ticks_diff(time.ticks_ms(), t_start)
        
        if duration > 1000: # ১ সেকেন্ডের বেশি হলে লং প্রেস
            return 2
        else:
            return 1
    return 0
# ১০টি ব্রাইটনেস লেভেল (০ থেকে ২৫৫ এর মধ্যে)
bright_levels = [1, 10, 25, 50, 75, 100, 130, 165, 210, 255]
bright_index = 9 # শুরুতে ফুল ব্রাইটনেস (২৫৫)

# --- গ্লোবাল ভেরিয়েবল ---
# সেটিংসের ভেতরের অপশন
menu_items = ["WAVEFORM", "4.2V BATT", "12.6V BATT", "OHM METER", "POWER ANALYZER", "LED TESTER", "CONTINUITY", "BRIGHTNESS"] # SETTINGS অ্যাড করলাম
brightness_level = 255 # ডিফল্ট ফুল ব্রাইটনেস

current_selection = 0
in_sub_menu = False
zzz_y = 0  # ঘুমের অ্যানিমেশনের শুরুর পজিশন
power_page = 0 
v_waveform = [63] * 128
c_waveform = [63] * 128
w_waveform = [63] * 128


last_activity = time.time()
screen_on = True

# --- ড্রয়িং ফাংশনস ---
def draw_batt_icon(x, y, pct):
    oled.rect(x, y, 32, 14, 1) 
    oled.fill_rect(x+32, y+4, 3, 6, 1) 
    fill_w = int((pct/100)*28)
    oled.fill_rect(x+2, y+2, fill_w, 10, 1)

def draw_res_icon(x, y):
    # দুই পাশের তার (Leads)
    oled.line(x, y+7, x+5, y+7, 1)      # বাম পাশের তার
    oled.line(x+27, y+7, x+32, y+7, 1)   # ডান পাশের তার
    
    # রেজিস্টরের বডি (ভরাট বক্স)
    oled.fill_rect(x+5, y+2, 22, 11, 1)
    
    # রেজিস্টরের কালার ব্যান্ড (কালার কোড বোঝাতে কাটা অংশ)
    oled.vline(x+8, y+2, 11, 0)   # ১ম ব্যান্ড
    oled.vline(x+12, y+2, 11, 0)  # ২য় ব্যান্ড
    oled.vline(x+18, y+2, 11, 0)  # ৩য় ব্যান্ড (মাল্টিপ্লায়ার)

def play_tone(freq, duration):
    try:
        buzzer.freq(freq); buzzer.duty_u16(30000)
        time.sleep(duration); buzzer.duty_u16(0)
    except: pass

def get_ina_data():
    try:
        v_raw = i2c_ina.readfrom_mem(0x40, 0x02, 2)
        v = ((v_raw[0] << 8 | v_raw[1]) >> 3) * 0.004
        c_raw = i2c_ina.readfrom_mem(0x40, 0x01, 2)
        curr = (c_raw[0] << 8 | c_raw[1])
        if curr > 32767: curr -= 65536
        c_ma = abs(curr * 0.1)
        return v, c_ma, (v * c_ma)
    except: return 0.0, 0.0, 0.0

def draw_header(title):
    oled.fill_rect(0, 0, 128, 12, 1)
    oled.text(title, 4, 2, 0)
    oled.hline(0, 13, 128, 1)
    
    
    
def draw_led_icon(x, y):
    # বাল্বের ভরাট অংশ (Body)
    oled.fill_rect(x+6, y+3, 13, 11, 1)  # মূল ভরাট গোল অংশ
    
    # বাল্বের তলার প্যাঁচানো অংশ (Screw Base)
    oled.fill_rect(x+9, y+14, 7, 2, 1)   # ১ম প্যাঁচ
    oled.fill_rect(x+10, y+17, 5, 2, 1)  # ২য় প্যাঁচ
    oled.pixel(x+12, y+19, 1)           # একবারে নিচের টিপ
    
    # আলো বা রশ্মি (Ray Lines)
    # তোর দেওয়া ছবির মতো চারদিকে রশ্মি
    oled.vline(x+12, y, 3, 1)           # একবারে উপরের সোজা রশ্মি
    
    oled.line(x+4, y+3, x+1, y+1, 1)    # বাম-উপরের কোণাকুণি
    oled.line(x+21, y+3, x+24, y+1, 1)  # ডান-উপরের কোণাকুণি
    
    oled.hline(x, y+8, 3, 1)            # একবারে বামের সোজা রশ্মি
    oled.hline(x+22, y+8, 3, 1)          # একবারে ডানের সোজা রশ্মি
    
    oled.line(x+4, y+14, x+1, y+16, 1)   # বাম-নিচের কোণাকুণি
    oled.line(x+21, y+14, x+24, y+16, 1) # ডান-নিচের কোণাকুণি

# --- বুট স্ক্রিন + অরিজিনাল বুট সাউন্ড ---
assets.show_splash(oled)
for f in [440, 659, 880, 1046]: # তোর সেই প্রিয় টোন
    play_tone(f, 0.12)
time.sleep(0.5)
def go_to_sleep():
    oled.fill(0)
    oled.text("Zzz...", 50, 30)
    oled.show()
    time.sleep(1)
    oled.poweroff() # ডিসপ্লে অফ
    
    
    
    # এখানে কোড আটকে থাকবে যতক্ষণ না তুই বাটন টিপছিস
    while True:
        if next_btn.value() == 0 or select_btn.value() == 0:
            play_tone(1200, 0.2)
            oled.poweron() # ডিসপ্লে অন
            # ব্রাইটনেস আবার আগের জায়গায় সেট করা
            oled.write_cmd(0x81)
            oled.write_cmd(brightness_level)
            time.sleep(0.5)
            break # লুপ থেকে বের হয়ে আবার মেনুতে যাবে

while True:
# নতুন ১ মিনিটের ডিম এবং ২ মিনিটের স্লিপ লজিক
    now = time.time()
    idle_time = now - last_activity  # <--- এই লাইনটা মাস্ট লাগবে!
    if idle_time > 120: 
        # --- এই নতুন অংশটুকু জেগে ওঠার জন্য ---
        if next_btn.value() == 0 or select_btn.value() == 0:
            last_activity = time.time() # সময় রিসেট
            screen_on = True
            oled.write_cmd(0x81)
            oled.write_cmd(bright_levels[bright_index]) # ব্রাইটনেস ঠিক করা
            play_tone(1200, 0.1) # জেগে ওঠার আওয়াজ
            time.sleep(0.2)
            continue # এখান থেকে ফিরে গিয়ে মেইন মেনু দেখাবে
        
        # --- তোর আগের অ্যানিমেশন কোড নিচে থাকবে ---
        if screen_on:
            oled.write_cmd(0x81); oled.write_cmd(1) 
            oled.fill(0)
            try:
                zzz_y = (zzz_y + 1) if zzz_y < 70 else -10
            except:
                zzz_y = 0
            oled.text("z", 60, zzz_y, 1)
            oled.text("Z", 75, zzz_y - 12, 1)
            oled.text("Zzz...", 45, zzz_y - 25, 1)
            oled.show()
            time.sleep(0.1)
            continue
            
    
    elif idle_time > 60: # ১ মিনিট পর ডিম (Dim)
        if screen_on:
            oled.write_cmd(0x81)
            oled.write_cmd(1) # আলো একদম কমে ১ হয়ে যাবে
    elif screen_on: # ১ মিনিটের নিচে থাকলে নরমাল আলো
        oled.write_cmd(0x81)
        oled.write_cmd(bright_levels[bright_index])

    # বাটন টিপলে জেগে ওঠার লজিক
    if next_btn.value() == 0 or select_btn.value() == 0:
        last_activity = now
        if not screen_on:
            oled.poweron()
            screen_on = True
            time.sleep(0.2) # বাটন ডিবাউন্স; screen_on = True; time.sleep(0.2)

    if not screen_on:
        time.sleep(0.1); continue

    if not in_sub_menu:
        oled.fill(0); draw_header("MODE SELECT")
        offset = 0
        if current_selection >= 4: offset = current_selection - 3
        
        # স্ক্রলবার
        scroll_h = int((1 / len(menu_items)) * 42)
        scroll_y = int((current_selection / len(menu_items)) * 42)
        oled.fill_rect(124, 18 + scroll_y, 3, scroll_h, 1)

        for i in range(4):
            idx = i + offset
            if idx < len(menu_items):
                y = 18 + (i * 11)
                if idx == current_selection:
                    oled.rect(0, y-2, 120, 11, 1)
                    oled.fill_rect(1, y-1, 118, 9, 1)
                    oled.text(menu_items[idx], 4, y, 0)
                else: oled.text(menu_items[idx], 6, y, 1)
        oled.show()

        if next_btn.value() == 0:
            current_selection = (current_selection + 1) % len(menu_items)
            play_tone(1200, 0.02); time.sleep(0.2)
        if select_btn.value() == 0:
            in_sub_menu = True; play_tone(1500, 0.08); time.sleep(0.3)

    else:
        oled.fill(0)
        v, c, w = get_ina_data()
        
        # তোর দেওয়া স্কেলিং: ২০ভি = টপ, ৫এ = টপ, ৩০ডব্লিউ = টপ
        # Waveform updates
        v_waveform.append(63 - int(min(v, 20) * 2.45)); v_waveform.pop(0)
        c_waveform.append(63 - int(min(c/1000, 5) * 9.8)); c_waveform.pop(0)
        w_waveform.append(63 - int(min(w/1000, 30) * 1.6)); w_waveform.pop(0)

        # --- POWER ANALYZER + GRAPH ---
        # --- POWER ANALYZER + GRAPH (পেজ সিস্টেম) ---
        if current_selection == 4:
            # বাটন টিপলে পেজ চেইঞ্জ হবে (০, ১, ২, ৩ - চারটা পেজ)
            if next_btn.value() == 0:
                power_page = (power_page + 1) % 4
                play_tone(1000, 0.05); time.sleep(0.2)
            
            oled.fill(0)
            if power_page == 0:
                draw_header("POWER DATA")
                oled.text("V: {:.2f} V".format(v), 5, 20)
                oled.text("C: {:.1f} mA".format(c), 5, 32)
                oled.text("W: {:.1f} mW".format(w), 5, 44)
                oled.text("-> NEXT:GRAPH", 10, 56)
            
            elif power_page == 1: # VOLT ANALYZER
                oled.fill(0)
                draw_header("V-GRAPH") # টাইটেল ছোট করলাম যাতে জায়গা বাঁচে
                oled.vline(7, 16, 48, 1) # স্কেল লাইন ১৬ পিক্সেল থেকে শুরু
                for volt in range(21):
                    y_pos = 63 - int(volt * 2.3) # স্কেলিং একটু কমালাম
                    if volt % 5 == 0: oled.hline(2, y_pos, 5, 1)
                    else: oled.hline(5, y_pos, 2, 1)
                
                v_waveform.append(63 - int(min(v, 20) * 2.3))
                v_waveform.pop(0)
                for x in range(len(v_waveform) - 12):
                    oled.line(x+10, v_waveform[x], x+11, v_waveform[x+1], 1)
                oled.text("{:.1f}V".format(v), 85, 2, 0) # হেডারের ভেতরে টেক্সট

            elif power_page == 2: # AMP ANALYZER
                oled.fill(0)
                draw_header("A-GRAPH")
                oled.vline(7, 16, 48, 1)
                for amp in range(51):
                    y_pos = 63 - int(amp * 0.94)
                    if amp % 10 == 0: oled.hline(2, y_pos, 5, 1)
                    elif amp % 5 == 0: oled.hline(4, y_pos, 3, 1)
                
                c_waveform.append(63 - int(min(c/1000, 5) * 9.4))
                c_waveform.pop(0)
                for x in range(len(c_waveform) - 12):
                    oled.line(x+10, c_waveform[x], x+11, c_waveform[x+1], 1)
                    oled.line(x+10, c_waveform[x]+1, x+11, c_waveform[x+1]+1, 1)
                oled.text("{:.2f}A".format(c/1000), 82, 2, 0)

            elif power_page == 3: # WATT ANALYZER
                oled.fill(0)
                draw_header("W-GRAPH")
                oled.vline(7, 16, 48, 1)
                for watt in range(31):
                    y_pos = 63 - int(watt * 1.5)
                    if watt % 5 == 0: oled.hline(2, y_pos, 5, 1)
                    else: oled.hline(5, y_pos, 2, 1)

                w_waveform.append(63 - int(min(w/1000, 30) * 1.5))
                w_waveform.pop(0)
                for x in range(len(w_waveform) - 12):
                    if x % 2 == 0: oled.pixel(x+10, w_waveform[x], 1)
                oled.text("{:.1f}W".format(w/1000), 82, 2, 0)

            oled.show()

        elif current_selection == 0: # WAVEFORM
            draw_header("WAVEFORM")
            
            for x in range(127): oled.line(x, v_waveform[x], x+1, v_waveform[x+1], 1)
            oled.text("{:.1f}V".format(v), 90, 18)

        elif current_selection == 3: # OHM METER
            draw_header("OHM METER"); draw_res_icon(50, 20)
            avg = sum([res_adc.read_u16() for _ in range(20)]) // 20
            
            if avg < 62000:
                vo = (avg * 3.3) / 65535
                res = max(0, (10000 * (vo / (3.3 - vo))) - 12)
                
                # ৫ ওহম এর নিচে গেলে বিপ সাউন্ড হবে
                if res <= 5.0:
                    oled.text("{:.1f} OHM".format(res), 35, 40)
                    oled.text("!!! SHORT !!!", 15, 53)
                    play_tone(2500, 0.05) # হালকা বিপ
                else:
                    text_val = "{:.1f} OHM".format(res) if res < 1000 else "{:.2f} K".format(res/1000)
                    oled.text(text_val, 40, 40)
            else:
                oled.text("OPEN", 47, 40)
                
        elif current_selection == 7:
            draw_header("BRIGHTNESS")
            
            # ১. ব্রাইটনেস বার (Progress Bar) আঁকা
            # বারের আউটলাইন
            oled.rect(14, 30, 100, 12, 1) 
            # বারের ভেতরের অংশ (১০টি ধাপ অনুযায়ী ফিল হবে)
            fill_width = (bright_index + 1) * 10
            oled.fill_rect(14, 30, fill_width, 12, 1)
            
            # ২. পার্সেন্টেজ এবং লেভেল দেখানো
            pct = (bright_index + 1) * 10
            oled.text(f"Level: {pct}%", 22, 45)
            
            
            
            # ৩. NEXT বাটন দিয়ে ব্রাইটনেস কমানো-বাড়ানো (১০ ধাপে)
            if next_btn.value() == 0:
                bright_index -= 1 # এক ধাপ কমবে
                if bright_index < 0: 
                    bright_index = 9 # আবার ১০০% এ ফিরে যাবে (Cycle)
                
                # আসল ব্রাইটনেস ভ্যালু সেট করা
                brightness_level = bright_levels[bright_index]
                oled.write_cmd(0x81)
                oled.write_cmd(brightness_level)
                
                play_tone(1000, 0.05)
                time.sleep(0.2) # দ্রুত পরিবর্তনের জন্য

            # ৪. SELECT বাটন দিয়ে ব্যাক করা
            if select_btn.value() == 0:
                play_tone(1200, 0.1)
                in_sub_menu = False
                time.sleep(0.4)
        elif current_selection == 1: # 4.2V BATT
            draw_header("4.2V BATT")
            p = max(0, min(100, (v - 3.0) / 1.2 * 100))
            draw_batt_icon(10, 30, p); oled.text("{:.2f}V {:.0f}%".format(v, p), 48, 33)

        elif current_selection == 2: # 12.6V BATT
            draw_header("12.6V BATT")
            p = max(0, min(100, (v - 9.0) / 3.6 * 100))
            draw_batt_icon(10, 30, p); oled.text("{:.2f}V {:.0f}%".format(v, p), 48, 33)

        elif current_selection == 5: # LED TESTER
            draw_header("LED TEST")
            led_probe.value(1)  # প্রোব অন (LED জ্বলা শুরু করবে)
            
            # নতুন আইকন ডিসপ্লের মাঝখানে আঁক (২৮x২০ পিক্সেল সাইজ)
            draw_led_icon(50, 25) 
            
            # নিচের লেখা
            oled.text("PROBE ON", 35, 52)

        elif current_selection == 6: # CONTINUITY
            draw_header("CONTINUITY")
            
            # রেজিস্ট্যান্স ক্যালকুলেশন (৫ ওহম চেক করার জন্য)
            avg = sum([res_adc.read_u16() for _ in range(10)]) // 10
            
            if avg < 62000: # যদি কিছু কানেক্ট করা থাকে
                vo = (avg * 3.3) / 65535
                # তোর ডিভাইসের ক্যালিব্রেশন অনুযায়ী রেজিস্ট্যান্স বের করা
                res = max(0, (10000 * (vo / (3.3 - vo))) - 12)
                
                # ৫ ওহম বা তার নিচে হলে বিপ বাজবে
                if res <= 5.0:
                    oled.fill_rect(10, 35, 108, 18, 1)
                    oled.text("SHORT!", 40, 40, 0)
                    play_tone(3000, 0.05) # বিপ সাউন্ড
                else:
                    oled.rect(10, 35, 108, 18, 1)
                    oled.text("{:.1f} Ohm".format(res), 35, 40)
            else:
                oled.rect(10, 35, 108, 18, 1)
                oled.text("OPEN/READY", 25, 40)

        oled.show()
        if select_btn.value() == 0: in_sub_menu = False; led_probe.value(0); time.sleep(0.3)
    time.sleep(0.01)
