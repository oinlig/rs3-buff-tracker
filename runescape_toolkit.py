"""RS3 Buff Tracker v0.6.0 — screen-based buff icon alerts and GitHub updater."""
import os, sys, json, time, threading, urllib.request, subprocess
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
APP_VERSION = "0.6.0"
REPO_RAW = "https://raw.githubusercontent.com/oinlig/rs3-buff-tracker/main/"
MANIFEST_URL = REPO_RAW + "version.json"
DATA_DIR = os.path.join(os.path.expanduser("~"), ".runescape_toolkit")
CONFIG = os.path.join(DATA_DIR, "settings_v05.json")
TEMPLATES = os.path.join(DATA_DIR, "buff_templates")
os.makedirs(TEMPLATES, exist_ok=True)
try:
    from PIL import Image, ImageGrab, ImageTk, ImageChops, ImageStat
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
        self.title("RS3 Buff Tracker v" + APP_VERSION)
        self.geometry("920x650")
        self.region = None
        self.buffs = {}
        self.monitoring = False
        self.seen = set()
        self.missing = {}
        self.alerted = set()
        self.load()
        top = ttk.Frame(self, padding=12); top.pack(fill="x")
        ttk.Label(top, text="RuneScape 3 Buff Tracker", font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Button(top, text="Check for updates", command=self.check_updates).pack(side="right")
        ttk.Button(top, text="Test sound", command=sound).pack(side="right", padx=6)
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status).pack(anchor="w", padx=14, pady=(0,8))
        row=ttk.Frame(self,padding=10); row.pack(fill="x")
        ttk.Button(row,text="Select buff-bar region",command=self.select_region).pack(side="left")
        ttk.Button(row,text="Capture preview",command=self.capture).pack(side="left",padx=5)
        self.monitor_btn=ttk.Button(row,text="Start monitoring",command=self.toggle); self.monitor_btn.pack(side="left")
        self.tree=ttk.Treeview(self,columns=("enabled","template","state"),show="headings",height=8)
        for c,t,w in [("enabled","Alert",80),("template","Icon template",180),("state","Recognition",160)]:
            self.tree.heading(c,text=t); self.tree.column(c,width=w,anchor="center")
        self.tree.pack(fill="x",padx=14,pady=8)
        row2=ttk.Frame(self,padding=10); row2.pack(fill="x")
        ttk.Button(row2,text="Add buff",command=self.add_buff).pack(side="left")
        ttk.Button(row2,text="Select icon from preview",command=self.select_icon).pack(side="left",padx=5)
        ttk.Button(row2,text="Toggle alert",command=self.toggle_alert).pack(side="left")
        ttk.Button(row2,text="Remove buff",command=self.remove_buff).pack(side="right")
        self.preview=ttk.Label(self,text="Select the buff-bar region, then capture a preview.",anchor="w")
        self.preview.pack(fill="both",expand=True,padx=14,pady=10)
        self.refresh()
        self.protocol("WM_DELETE_WINDOW",self.close)

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
            self.tree.insert("","end",iid=n,values=("On" if b.get("enabled",True) else "Off","Ready" if ok else "Missing",b.get("state","Not scanned")))

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
        b=b.resize(a.size).convert("L"); a=a.convert("L")
        return max(0,1-ImageStat.Stat(ImageChops.difference(a,b)).mean[0]/255)

    def scan(self):
        try:
            im=self.crop(); out={}
            for n,b in list(self.buffs.items()):
                path=os.path.join(TEMPLATES,b.get("template",""))
                if not b.get("template") or not os.path.isfile(path): out[n]="Missing template"; continue
                templ=Image.open(path).convert("RGB"); tw,th=templ.size
                best=0; stride=max(2,min(5,tw//8))
                if tw>im.width or th>im.height: out[n]="Invalid template"; continue
                for y in range(0,im.height-th+1,stride):
                    for x in range(0,im.width-tw+1,stride):
                        score=self.similarity(templ,im.crop((x,y,x+tw,y+th)))
                        best=max(best,score)
                found=best>=0.90; out[n]="Detected" if found else "Not detected"
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
        self.monitor_btn.configure(text="Stop monitoring" if self.monitoring else "Start monitoring")
        self.status.set("Monitoring screen region" if self.monitoring else "Monitoring stopped")
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
            req=urllib.request.Request(MANIFEST_URL,headers={"User-Agent":"RS3-Buff-Tracker"})
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
            with open(updater,"w",encoding="utf-8") as f:
                f.write('@echo off\r\nsetlocal\r\ntimeout /t 2 /nobreak >nul\r\ncopy /y "%~1" "%~2" >nul\r\nif errorlevel 1 (echo Update failed. & pause & exit /b 1)\r\ndel "%~1"\r\nstart "" "%~3"\r\n')
            script=os.path.abspath(__file__); bat=os.path.join(os.path.dirname(script),"run_toolkit.bat")
            self.after(0,lambda:self.start_update(latest,staged,script,updater,bat))
        except Exception as e:
            self.after(0,lambda err=str(e):(self.status.set("Update failed"),messagebox.showerror("Update failed","Current version was not changed.\n\n"+err,parent=self)))

    def start_update(self,latest,staged,script,updater,bat):
        if not messagebox.askyesno("Update available","Version "+latest+" is available. Install now? The app will restart; saved settings and icon templates stay in place.",parent=self):
            try: os.remove(staged)
            except OSError: pass
            return
        try:
            # Quote each batch argument so folders containing spaces work.
            subprocess.Popen('start "" "'+updater+'" "'+staged+'" "'+script+'" "'+bat+'"',shell=True,cwd=os.path.dirname(script))
            self.close()
        except Exception as e: messagebox.showerror("Updater error",str(e),parent=self)

    def close(self):
        self.monitoring=False
        try: self.save()
        except Exception: pass
        self.destroy()

if __name__=="__main__":
    App().mainloop()
