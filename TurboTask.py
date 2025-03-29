import tkinter as tk
from tkinter import ttk, messagebox
from pynput import mouse, keyboard
import threading
import time
import sys
import os
import screeninfo

if sys.platform == "win32":
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

class MacroRecorder:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TurboTask")
        self.root.geometry("450x600")
        self.root.configure(bg='#2C3E50')
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.recording = False
        self.current_button = None
        self.buttons = {}
        self.stop_playback = {}
        self.start_time = None
        self.hotkeys = {}
        self.waiting_for_hotkey = None
        self.initial_mouse_pos = None
        self.keyboard_controller = keyboard.Controller()
        self.mouse_controller = mouse.Controller()
        self.screen = screeninfo.get_monitors()[0]
        self.screen_width = self.screen.width
        self.screen_height = self.screen.height
        self.create_gui()
        self.mouse_listener = None
        self.keyboard_listener = None
        self.hotkey_listener = keyboard.Listener(on_press=self.check_hotkey)
        self.hotkey_listener.start()

    def create_gui(self):
        title = tk.Label(self.root, text="TurboTask", font=("Helvetica", 18, "bold"),
                        bg='#2C3E50', fg='white')
        title.pack(pady=20)

        stop_all_btn = ttk.Button(self.root, text="Stop All", command=self.stop_all_playback,
                               style='TButton')
        stop_all_btn.pack(pady=10)

        for i in range(5):
            frame = tk.Frame(self.root, bg='#2C3E50')
            frame.pack(pady=5)

            repeat_entry = ttk.Entry(frame, width=5, justify='center')
            repeat_entry.insert(0, "1")
            repeat_entry.pack(side=tk.LEFT, padx=5)

            btn = ttk.Button(frame, text=f"Macro {i+1}", width=15,
                           command=lambda x=i: self.toggle_recording(x))
            btn.pack(side=tk.LEFT, padx=5)

            hotkey_btn = ttk.Button(frame, text="Set Hotkey",
                                 command=lambda x=i: self.set_hotkey(x),
                                 width=10)
            hotkey_btn.pack(side=tk.LEFT, padx=5)

            loop_var = tk.BooleanVar()
            loop_check = ttk.Checkbutton(frame, text="Repeat", variable=loop_var)
            loop_check.pack(side=tk.LEFT, padx=5)

            self.buttons[i] = {
                'button': btn,
                'repeat_entry': repeat_entry,
                'hotkey_button': hotkey_btn,
                'events': [],
                'recording': False,
                'hotkey': None,
                'start_position': None,
                'loop_var': loop_var
            }
            self.stop_playback[i] = False

        footer = tk.Label(self.root, text="by asakue", font=("Helvetica", 10),
                         bg='#2C3E50', fg='#7F8C8D')
        footer.pack(side=tk.BOTTOM, pady=10)

    def set_hotkey(self, button_id):
        if self.waiting_for_hotkey is not None:
            return
        
        self.waiting_for_hotkey = button_id
        self.buttons[button_id]['hotkey_button'].configure(text="Press Key")
        self.root.update()

    def check_hotkey(self, key):
        if key is None:
            return
        try:
            key_str = str(key).replace("Key.", "").replace("'", "")
            
            if key_str == "backspace":
                self.stop_all_playback()
                return
            if self.waiting_for_hotkey is not None:
                button_id = self.waiting_for_hotkey
                if key_str in self.hotkeys and self.hotkeys[key_str] != button_id:
                    messagebox.showwarning("Warning", f"Key {key_str} is already in use!")
                else:
                    old_hotkey = self.buttons[button_id]['hotkey']
                    if old_hotkey and old_hotkey in self.hotkeys:
                        del self.hotkeys[old_hotkey]
                    
                    self.hotkeys[key_str] = button_id
                    self.buttons[button_id]['hotkey'] = key_str
                    self.buttons[button_id]['hotkey_button'].configure(
                        text=f"Key: {key_str}"
                    )
                self.waiting_for_hotkey = None
                return
            if key_str in self.hotkeys:
                button_id = self.hotkeys[key_str]
                if not self.buttons[button_id]['recording']:
                    self.stop_all_playback()
                    self.current_button = button_id
                    self.buttons[button_id]['events'] = []
                    self.recording = True
                    self.buttons[button_id]['recording'] = True
                    self.buttons[button_id]['button'].configure(text="Stop Recording")
                    self.start_time = time.perf_counter()
                    self.initial_mouse_pos = self.mouse_controller.position
                    self.buttons[button_id]['start_position'] = self.initial_mouse_pos
                    self.start_listeners()
                else:
                    self.recording = False
                    self.buttons[button_id]['recording'] = False
                    self.buttons[button_id]['button'].configure(text=f"Macro {button_id+1}")
                    self.stop_listeners()
                    if self.buttons[button_id]['events']:
                        repeat_count = self.get_repeat_count(button_id)
                        self.stop_playback[button_id] = False
                        threading.Thread(target=self.playback,
                                       args=(button_id, repeat_count),
                                       daemon=True).start()
        except Exception as e:
            print(f"Hotkey error: {e}")

    def get_repeat_count(self, button_id):
        try:
            if self.buttons[button_id]['loop_var'].get():
                return 0  # 0 означает бесконечное повторение
            count = int(self.buttons[button_id]['repeat_entry'].get())
            return max(1, count)
        except ValueError:
            return 1

    def on_move(self, x, y):
        if self.recording and self.current_button is not None:
            current_time = time.perf_counter() - self.start_time
            x = max(0, min(x, self.screen_width - 1))
            y = max(0, min(y, self.screen_height - 1))
            self.buttons[self.current_button]['events'].append(('move', (x, y), current_time))

    def on_click(self, x, y, button, pressed):
        if self.recording and self.current_button is not None:
            current_time = time.perf_counter() - self.start_time
            x = max(0, min(x, self.screen_width - 1))
            y = max(0, min(y, self.screen_height - 1))
            self.buttons[self.current_button]['events'].append(('click', (x, y, button, pressed), current_time))

    def on_press(self, key):
        if self.recording and self.current_button is not None:
            current_time = time.perf_counter() - self.start_time
            try:
                self.buttons[self.current_button]['events'].append(('key_press', key, current_time))
            except Exception as e:
                print(f"Key press error: {e}")

    def on_release(self, key):
        if self.recording and self.current_button is not None:
            current_time = time.perf_counter() - self.start_time
            try:
                self.buttons[self.current_button]['events'].append(('key_release', key, current_time))
            except Exception as e:
                print(f"Key release error: {e}")

    def start_listeners(self):
        self.stop_listeners()
        try:
            self.mouse_listener = mouse.Listener(
                on_move=self.on_move,
                on_click=self.on_click,
                suppress=False
            )
            self.keyboard_listener = keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release,
                suppress=False
            )
            self.mouse_listener.start()
            self.keyboard_listener.start()
        except Exception as e:
            print(f"Listener start error: {e}")

    def stop_listeners(self):
        try:
            if self.mouse_listener and self.mouse_listener.is_alive():
                self.mouse_listener.stop()
                self.mouse_listener = None
            if self.keyboard_listener and self.keyboard_listener.is_alive():
                self.keyboard_listener.stop()
                self.keyboard_listener = None
        except Exception as e:
            print(f"Listener stop error: {e}")

    def stop_all_playback(self):
        for i in range(5):
            self.stop_playback[i] = True

    def playback(self, button_id, repeat_count):
        events = self.buttons[button_id]['events'].copy()
        start_pos = self.buttons[button_id]['start_position']
        if not events or not start_pos:
            return
        
        self.current_button = button_id  
        iteration = 0
        while iteration < repeat_count or repeat_count == 0:
            if self.stop_playback[button_id]:
                break
                
            try:
                start_playback_time = time.perf_counter()
                self.mouse_controller.position = start_pos
                time.sleep(0.05)  
                
                last_x, last_y = start_pos
                last_time = 0
                
                for event in events:
                    if self.stop_playback[button_id]:
                        break
                        
                    event_type, event_data, event_time = event
                    wait_time = max(0, event_time - (time.perf_counter() - start_playback_time))
                    
                    if wait_time > 0.001:
                        time.sleep(wait_time)
                    
                    try:
                        if event_type == 'move':
                            x, y = event_data
                            self.mouse_controller.position = (x, y)
                            last_x, last_y = x, y
                        elif event_type == 'click':
                            x, y, button, pressed = event_data
                            self.mouse_controller.position = (x, y)
                            if pressed:
                                self.mouse_controller.press(button)
                            else:
                                self.mouse_controller.release(button)
                            last_x, last_y = x, y
                        elif event_type == 'key_press':
                            self.keyboard_controller.press(event_data)
                        elif event_type == 'key_release':
                            self.keyboard_controller.release(event_data)
                        last_time = event_time
                    except Exception as e:
                        print(f"Playback event error: {e}")
                        
            except Exception as e:
                print(f"Playback loop error: {e}")
            
            iteration += 1

    def on_closing(self):
        try:
            self.stop_all_playback()
            self.stop_listeners()
            if self.hotkey_listener and self.hotkey_listener.is_alive():
                self.hotkey_listener.stop()
            self.root.destroy()
        except Exception as e:
            print(f"Closing error: {e}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = MacroRecorder()
    app.run()
