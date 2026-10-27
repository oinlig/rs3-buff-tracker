"""RS3 Buff Monitor v0.7.3 — edge-based matching to reduce background sensitivity."""
import os, sys, json, time, threading, urllib.request, subprocess
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
APP_VERSION = "0.7.3"
REPO_RAW = "https://raw.githubusercontent.com/oinlig/rs3-buff-tracker/main/"
MANIFEST_URL = REPO_RAW + "version.json"
DATA_DIR = os.path.join(os.path.expanduser("~"), ".runescape_toolkit")
CONFIG = os.path.join(DATA_DIR, "settings_v05.json")
TEMPLATES = os.path.join(DATA_DIR, "buff_templates")
os.makedirs(TEMPLATES, exist_ok=True)
try:
    from PIL import Image, ImageGrab, ImageTk, ImageChops, ImageStat, ImageFilter
    PIL_OK = True
except ImportError:
    PIL_OK = False

def sound():
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass

def ver(v):
    try: return tuple(int(x) for x in str(v).lstrip("v").split("."))
    except Exception: return (0,)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RS3 Buff Monitor")
        self.geometry("1060x760")
        self.minsize(860, 650)
        self.configure(bg="#0b1020")
        self.region = None
        self.buffs = {}
        self.monitoring = False
        self.seen = set()
        self.missing = {}
        self.alerted = set()
        self.load()

        # Custom dark interface: navy surfaces, crisp typography, teal accent.
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except tk.TclError: pass
        self.colors = {"bg":"#0b1020", "panel":"#121a2b", "panel2":"#172238",
                       "text":"#eef4ff", "muted":"#93a4c4", "accent":"#48e0c1",
                       "accent_dark":"#163e43", "line":"#26344d", "selected":"#24465a"}
        self.option_add("*Font", ("Segoe UI", 10))
        style.configure(".", background=self.colors["bg"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("TFrame", background=self.colors["bg"])
        style.configure("Panel.TFrame", background=self.colors["panel"])
        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"])
        style.configure("Muted.TLabel", background=self.colors["panel"], foreground=self.colors["muted"])
        style.configure("Hero.TLabel", background=self.colors["bg"], foreground=self.colors["text"], font=("Segoe UI", 23, "bold"))
        style.configure("Eyebrow.TLabel", background=self.colors["bg"], foreground=self.colors["accent"], font=("Segoe UI", 9, "bold"))
        style.configure("Status.TLabel", background=self.colors["panel"], foreground=self.colors["accent"], font=("Segoe UI", 10, "bold"), padding=(12, 10))
        style.configure("TButton", background=self.colors["panel2"], foreground=self.colors["text"], bordercolor=self.colors["line"], padding=(13, 9), relief="flat")
        style.map("TButton", background=[("active", "#24324c"), ("pressed", self.colors["accent_dark"])], foreground=[("active", self.colors["accent"])])
        style.configure("Accent.TButton", background=self.colors["accent"], foreground="#07131d", padding=(15, 10), font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#7af4dc"), ("pressed", "#31bfa5")], foreground=[("active", "#07131d")])
        style.configure("Treeview", background=self.colors["panel"], fieldbackground=self.colors["panel"], foreground=self.colors["text"], rowheight=36, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=self.colors["panel2"], foreground=self.colors["muted"], font=("Segoe UI", 9, "bold"), padding=(10, 11), relief="flat")
        style.map("Treeview", background=[("selected", self.colors["selected"])], foreground=[("selected", "#ffffff")])
        style.configure("TSeparator", background=self.colors["line"])

        # Header
        top = ttk.Frame(self, padding=(26, 22, 26, 14)); top.pack(fill="x")
        brand = ttk.Frame(top); brand.pack(side="left", fill="x", expand=True)
        ttk.Label(brand, text="RUNESCAPE 3  /  DESKTOP TOOL", style="Eyebrow.TLabel").pack(anchor="w")
        ttk.Label(brand, text="Buff Monitor", style="Hero.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Label(brand, text="BUFF STATUS  •  VISUAL MONITORING  •  AUDIO ALERTS", foreground=self.colors["muted"]).pack(anchor="w", pady=(4, 0))
        ttk.Button(top, text="Check for updates", command=self.check_updates).pack(side="right", padx=(8, 0), pady=10)
        ttk.Button(top, text="Test sound  ♪", command=sound).pack(side="right", pady=10)

        self.status = tk.StringVar(value="●  READY  —  Select your buff-bar region to begin")
        statusbar = ttk.Frame(self, style="Panel.TFrame", padding=(8, 0)); statusbar.pack(fill="x", padx=26, pady=(0, 16))
        ttk.Label(statusbar, textvariable=self.status, style="Status.TLabel").pack(fill="x")

        # Setup controls
        setup = ttk.Frame(self, style="Panel.TFrame", padding=16); setup.pack(fill="x", padx=26, pady=(0, 14))
        ttk.Label(setup, text="01  /  CAPTURE SETUP", style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        actions = ttk.Frame(setup, style="Panel.TFrame"); actions.pack(fill="x")
        ttk.Button(actions, text="Select buff-bar region", command=self.select_region, style="Accent.TButton").pack(side="left")
        ttk.Button(actions, text="Refresh preview", command=self.capture).pack(side="left", padx=8)
        self.monitor_btn = ttk.Button(actions, text="▶  Start monitoring", command=self.toggle)
        self.monitor_btn.pack(side="right")

        # Buff list
        listing = ttk.Frame(self, style="Panel.TFrame", padding=16); listing.pack(fill="x", padx=26, pady=(0, 14))
        ttk.Label(listing, text="02  /  YOUR BUFFS", style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
        self.tree = ttk.Treeview(listing, columns=("enabled","template","state"), show="tree headings", height=5)
        self.tree.heading("#0", text="BUFF NAME")
        self.tree.column("#0", width=300, minwidth=180, stretch=True)
        for col, heading, width in [("enabled","ALERT",90),("template","ICON TEMPLATE",190),("state","RECOGNITION",190)]:
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, anchor="center")
        self.tree.pack(fill="x", expand=True)
        row2 = ttk.Frame(listing, style="Panel.TFrame"); row2.pack(fill="x", pady=(12, 0))
        ttk.Button(row2, text="+  Add buff", command=self.add_buff, style="Accent.TButton").pack(side="left")
        ttk.Button(row2, text="Select icon from preview", command=self.select_icon).pack(side="left", padx=8)
        ttk.Button(row2, text="Toggle alert", command=self.toggle_alert).pack(side="left")
        ttk.Button(row2, text="Remove buff", command=self.remove_buff).pack(side="right")

        # Preview area
        preview_panel = ttk.Frame(self, style="Panel.TFrame", padding=16); preview_panel.pack(fill="both", expand=True, padx=26, pady=(0, 22))
        ttk.Label(preview_panel, text="03  /  LIVE REGION PREVIEW", style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
        self.preview = ttk.Label(preview_panel, text="No capture yet. Select your buff-bar region, then refresh the preview.", anchor="center", justify="center", padding=18, style="Muted.TLabel")
        self.preview.pack(fill="both", expand=True)
        self.refresh()
        self.protocol("WM_DELETE_WINDOW", self.close)
        if self.region:
            self.after(350, self.capture)

    def load(self):
        try:
            with open(CONFIG,encoding="utf-8") as f:
                c=json.load(f); self.region=c.get("region"); self.buffs=c.get("buffs",{})
        except Exception: pass

    def save(self):
        with open(CONFIG,"w",encoding="utf-8") as f:
            json.dump({"region":self.region,"buffs":self.buffs},f,indent=2)

    def refresh(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for n,b in self.buffs.items():
            ok=bool(b.get("template")) and os.path.isfile(os.path.join(TEMPLATES,b.get("template","")))
            self.tree.insert("","end",iid=n,text=n,values=("ON" if b.get("enabled",True) else "OFF","READY" if ok else "MISSING",b.get("state","Not scanned")))

    def selected(self):
        s=self.tree.selection()
        return s[0] if s else None

    def select_region(self):
        if not PIL_OK: return messagebox.showerror("Pillow needed","Run the launcher again; it installs Pillow.")
        self.withdraw(); self.after(250,self.region_overlay)

    def region_overlay(self):
        try:
            im=ImageGrab.grab(); w=tk.Toplevel(self); w.attributes("-fullscreen",True); w.attributes("-topmost",True)
            photo=ImageTk.PhotoImage(im); cv=tk.Canvas(w,width=im.width,height=im.height,cursor="crosshair"); cv.pack(fill="both",expand=True); cv.create_image(0,0,image=photo,anchor="nw"); w.photo=photo
            p={}; rect=[None]
            def down(e): p["x"],p["y"]=e.x,e.y; rect[0]=cv.create_rectangle(e.x,e.y,e.x,e.y,outline="#00ff99",width=3)
            def drag(e):
                if rect[0]: cv.coords(rect[0],p["x"],p["y"],e.x,e.y)
            def up(e):
                x1,x2=sorted((p["x"],e.x)); y1,y2=sorted((p["y"],e.y))
                if x2-x1<10 or y2-y1<10: return
                self.region=[x1,y1,x2,y2]; w.destroy(); self.deiconify(); self.save(); self.capture()
            cv.bind("<ButtonPress-1>",down); cv.bind("<B1-Motion>",drag); cv.bind("<ButtonRelease-1>",up)
            w.bind("<Escape>",lambda e:(w.destroy(),self.deiconify()))
        except Exception as e:
            self.deiconify(); messagebox.showerror("Screen selection failed",str(e))

    def crop(self):
        if not PIL_OK: raise RuntimeError("Pillow is missing. Run run_toolkit.bat.")
        if not self.region: raise RuntimeError("Select the buff-bar region first.")
        return ImageGrab.grab().crop(tuple(self.region))

    def capture(self):
        try:
            self.current=self.crop()
            display=self.current.copy(); display.thumbnail((850,260))
            self.photo=ImageTk.PhotoImage(display)
            self.preview.configure(image=self.photo,text="Preview refreshed. Select a buff, then select its icon.",compound="top")
            self.status.set("Preview refreshed")
        except Exception as e: messagebox.showerror("Capture failed",str(e))

    def add_buff(self):
        n=simpledialog.askstring("Add buff","Buff name:",parent=self)
        if not n: return
        n=n.strip()
        if not n or n in self.buffs: return messagebox.showerror("Buff name","Name is empty or already exists.")
        self.buffs[n]={"enabled":True,"template":""}; self.save(); self.refresh(); self.tree.selection_set(n)

    def select_icon(self):
        n=self.selected()
        if not n: return messagebox.showinfo("Select buff","Select a buff row first.")
        if not hasattr(self,"current"):
            self.capture()
            if not hasattr(self,"current"): return
        orig=self.current.copy(); disp=orig.copy(); disp.thumbnail((850,300))
        sx=orig.width/disp.width; sy=orig.height/disp.height
        win=tk.Toplevel(self); win.title("Select "+n+" icon")
        photo=ImageTk.PhotoImage(disp); win.photo=photo
        ttk.Label(win,text="Drag a tight box around the icon, then save.").pack(anchor="w",padx=8,pady=8)
        cv=tk.Canvas(win,width=disp.width,height=disp.height,cursor="crosshair"); cv.pack(padx=8); cv.create_image(0,0,image=photo,anchor="nw")
        p={}; rect=[None]
        def down(e): p["x"],p["y"]=e.x,e.y; rect[0]=cv.create_rectangle(e.x,e.y,e.x,e.y,outline="#00ff99",width=2)
        def drag(e):
            if rect[0]: cv.coords(rect[0],p["x"],p["y"],e.x,e.y)
        def up(e): p["end"]=(e.x,e.y)
        cv.bind("<ButtonPress-1>",down); cv.bind("<B1-Motion>",drag); cv.bind("<ButtonRelease-1>",up)
        def save():
            if "end" not in p: return messagebox.showerror("Select icon","Drag a box first.",parent=win)
            x1,x2=sorted((p["x"],p["end"][0])); y1,y2=sorted((p["y"],p["end"][1]))
            box=(int(x1*sx),int(y1*sy),int(x2*sx),int(y2*sy))
            if box[2]-box[0]<8 or box[3]-box[1]<8: return messagebox.showerror("Selection too small","Select a larger box.",parent=win)
            fn="icon_"+str(abs(hash(n)))+".png"; orig.crop(box).save(os.path.join(TEMPLATES,fn))
            self.buffs[n]["template"]=fn; self.save(); self.refresh(); win.destroy()
        ttk.Button(win,text="Save selected icon",command=save).pack(anchor="w",padx=8,pady=8)

    def toggle_alert(self):
        n=self.selected()
        if n: self.buffs[n]["enabled"]=not self.buffs[n].get("enabled",True); self.save(); self.refresh()

    def remove_buff(self):
        n=self.selected()
        if n and messagebox.askyesno("Remove buff","Remove "+n+"?"):
            self.buffs.pop(n,None); self.save(); self.refresh()

    def similarity(self,a,b):
        # Compare edge structure instead of raw pixel colors. This makes the
        # match less sensitive to changing scenery/background colors behind
        # the buff, while still comparing the icon's shape and detail.
        b=b.resize(a.size).convert("L").filter(ImageFilter.FIND_EDGES)
        a=a.convert("L").filter(ImageFilter.FIND_EDGES)
        return max(0,1-ImageStat.Stat(ImageChops.difference(a,b)).mean[0]/255)

    def scan(self):
        try:
            im=self.crop(); out={}
            for n,b in list(self.buffs.items()):
                path=os.path.join(TEMPLATES,b.get("template",""))
                if not b.get("template") or not os.path.isfile(path): out[n]="Missing template"; continue
                templ=Image.open(path).convert("RGB"); tw,th=templ.size
                best=0; stride=max(1,min(3,tw//12))
                if tw>im.width or th>im.height: out[n]="Invalid template"; continue
                for y in range(0,im.height-th+1,stride):
                    for x in range(0,im.width-tw+1,stride):
                        score=self.similarity(templ,im.crop((x,y,x+tw,y+th)))
                        best=max(best,score)
                found=best>=0.76; out[n]=("Detected ("+str(round(best*100))+"%)") if found else ("Not detected ("+str(round(best*100))+"%)")
                if found:
                    self.seen.add(n); self.missing[n]=0; self.alerted.discard(n)
                elif n in self.seen and b.get("enabled",True) and n not in self.alerted:
                    self.missing[n]=self.missing.get(n,0)+1
                    if self.missing[n]>=3:
                        self.alerted.add(n); self.after(0,lambda name=n:self.alert(name))
            self.after(0,lambda result=out:self.apply_results(result))
        except Exception as e: self.after(0,lambda err=str(e):self.status.set("Scan error: "+err))

    def apply_results(self,out):
        for n,s in out.items():
            if n in self.buffs: self.buffs[n]["state"]=s
        self.refresh(); self.status.set("Screen scan updated")

    def alert(self,n):
        sound(); self.status.set(n+" disappeared from the monitored region")
        messagebox.showinfo("Buff no longer detected",n+" is no longer detected. It may have expired, but this visual prototype can miss icons.")

    def toggle(self):
        if not PIL_OK: return messagebox.showerror("Pillow needed","Run run_toolkit.bat.")
        if not self.region: return messagebox.showinfo("Select region","Select the buff-bar region first.")
        self.monitoring=not self.monitoring
        self.monitor_btn.configure(text="■  Stop monitoring" if self.monitoring else "▶  Start monitoring")
        self.status.set("●  MONITORING  —  Scanning your buff bar" if self.monitoring else "●  READY  —  Monitoring stopped")
        if self.monitoring: self.loop()

    def loop(self):
        if not self.monitoring: return
        threading.Thread(target=self.scan,daemon=True).start()
        self.after(800,self.loop)

    def check_updates(self):
        self.status.set("Checking GitHub for updates…")
        threading.Thread(target=self.update_worker,daemon=True).start()

    def update_worker(self):
        try:
            req=urllib.request.Request(MANIFEST_URL + "?t=" + str(int(time.time())),headers={"User-Agent":"RS3-Buff-Tracker","Cache-Control":"no-cache","Pragma":"no-cache"})
            with urllib.request.urlopen(req,timeout=12) as r: m=json.loads(r.read().decode("utf-8"))
            latest=str(m["version"]); url=m["script_url"]
            if not url.startswith(REPO_RAW): raise ValueError("Manifest script URL is not trusted.")
            if ver(latest)<=ver(APP_VERSION):
                self.after(0,lambda:(self.status.set("You're up to date."),messagebox.showinfo("No updates","You're already using v"+APP_VERSION+".",parent=self))); return
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"RS3-Buff-Tracker"}),timeout=20) as r: code=r.read()
            text=code.decode("utf-8")
            if 'APP_VERSION = "' not in text or "class App(" not in text: raise ValueError("Downloaded file did not pass basic checks.")
            staged=os.path.abspath(__file__)+".update"
            with open(staged,"wb") as f: f.write(code)
            updater=os.path.join(os.path.dirname(os.path.abspath(__file__)),"apply_update.bat")
            script=os.path.abspath(__file__); bat=os.path.join(os.path.dirname(script),"run_toolkit.bat")
            # Put quoted paths directly into the batch file instead of passing
            # several nested quoted arguments through cmd.exe's START command.
            def q(path):
                return '"' + os.path.abspath(path).replace('"','') + '"'
            with open(updater,"w",encoding="utf-8") as f:
                f.write('@echo off\r\nsetlocal\r\ntimeout /t 2 /nobreak >nul\r\n')
                f.write('copy /y ' + q(staged) + ' ' + q(script) + ' >nul\r\n')
                f.write('if errorlevel 1 (echo Update failed. Could not replace the script. & pause & exit /b 1)\r\n')
                f.write('del ' + q(staged) + ' >nul 2>nul\r\n')
                f.write('start "" ' + q(bat) + '\r\n')
            self.after(0,lambda:self.start_update(latest,staged,script,updater,bat))
        except Exception as e:
            self.after(0,lambda err=str(e):(self.status.set("Update failed"),messagebox.showerror("Update failed","Current version was not changed.\n\n"+err,parent=self)))

    def start_update(self,latest,staged,script,updater,bat):
        if not messagebox.askyesno("Update available","Version "+latest+" is available. Install now? The app will restart; saved settings and icon templates stay in place.",parent=self):
            try: os.remove(staged)
            except OSError: pass
            return
        try:
            # Launch the updater batch directly; it contains its own quoted paths.
            subprocess.Popen(["cmd.exe", "/c", "start", "", updater], cwd=os.path.dirname(script), shell=False)
            self.close()
        except Exception as e: messagebox.showerror("Updater error",str(e),parent=self)

    def close(self):
        self.monitoring=False
        try: self.save()
        except Exception: pass
        self.destroy()

if __name__=="__main__":
    App().mainloop()
