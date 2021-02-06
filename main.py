from __future__ import annotations
import datetime
from typing import List, Dict
import re
import os
from datetime import datetime

from FTP import FTP
from Log import Log, LogOpen

class Action():
    def __init__(self):
        self.Date: datetime=None
        self.Editor: str=""
        self.ConSeries: str=""
        self.Convention: str=""
        self.Name: str=""
        self.Pages: int=0
        self.Bytes: int=0

    def IsEmpty(self) -> bool:
        if len(self.Editor) > 0:
            return False
        if len(self.ConSeries) > 0:
            return False
        if len(self.Convention) > 0:
            return False
        if len(self.Name) > 0:
            return False
        if self.Date is not None:
            return False
        return True


# Key is con series name; Value is Dict of con instance names.
#       For this Dict, its key is the ConInstance name, its value is a list of files
class Conlist():
    def __init__(self):
        self.List: Dict[str, Dict[str, List[str]]]={}
        self.Itemcount: int=0

    def Append(self, Series: str="", Instance: str="", File: str=""):
        if len(Series) > 0 and len(Instance) > 0 and len(File) > 0:
            if Series not in self.List.keys():
                self.List[Series]={}
            if Instance not in self.List[Series].keys():
                self.List[Series][Instance]=[]
            self.List[Series][Instance].append(File)
            self.Itemcount+=1


class Accumulator():
    def __init__(self):
        self.ConList: Conlist=Conlist()
        self.Pagecount: int=0
        self.Bytecount: int=0


#####################################################################

LogOpen("Log -- ConEditorLogAnalyzer.txt", "Log (Errors) -- ConEditorLogAnalyzer.txt")

f=FTP()

if not f.OpenConnection("FTP Credentials.json"):
    Log("Main: OpenConnection('FTP Credentials.json' failed")
    exit(0)

lines=FTP().GetFileAsString("", "updatelog.txt").replace("/n", "").split("\n")

actions: List[Action]=[]

# The pattern of lines that we care about is
#       "Uploaded ConInstance: <conseries>;<coninstance> [conpubs@fanac.org <datetime>]
#   followed by one or more lines which might include this type:
#       >>add: Source=<name>; Sitename=<name>; Display=<name>; URL=<url>; Size=<num>; Pages=<num>
isinUpload: bool=False
conseries=""
coninstance=""
date=None
editor=""
for line in lines:
    # When we come across a line that starts "Uploaded ConInstance:", we save the con instance for use in any subsequenr actions
    if line.startswith("Uploaded ConInstance: "):
        m=re.match("Uploaded ConInstance: (.+?):(.+?)\s+\[conpubs@fanac.org\s+(.+?)]$", line)
        if m is not None:
            conseries=m.groups()[0]
            coninstance=m.groups()[1]
            datetimestring=m.groups()[2].split()
            date=datetime.strptime(" ".join(datetimestring[0:6]), "%A %B %d, %Y  %I:%M:%S %p")
        continue
    if line.startswith("ConEditor starting.   "):
        m=re.match("ConEditor starting\.\s+\[(.+?)@fanac\.org\s", line)
        if m is not None:
            editor=m.groups()[0]
        continue

    if line.startswith(">>add: "):
        action=Action()
        action.ConSeries=conseries
        action.Convention=coninstance
        action.Editor=editor
        action.Date=date
        m=re.match(">>add: Source=.+?; Sitename=.+?; Display=(.+?); URL=.+?; Size=(\d*); Pages=(\d*);", line)
        if m is not None:
            action.Name=m.groups()[0]
            action.Bytes=int(m.groups()[1])
            action.Pages=int(m.groups()[2])
        actions.append(action)

# If we have a "Last time.txt" file, strip out all activity before that time.
# This file is created at the end of processing, so that the next time ConEditorLogAnalyzer runs, it only lists new stuff.
lines=[]
try:
    with open("Last time.txt", "r") as f:
        lines=f.readlines()
        lines=[l.strip() for l in lines if len(l.strip()) > 0 and l.strip()[0] != "#"]    # Remove empty lines and lines starting with "#"
    if len(lines) > 0:
        startdatetime=datetime.strptime(lines[0], "%B %d, %Y  %I:%M:%S %p")
        # Remove all actions occuring before startdatetime
        actions=[a for a in actions if a.Date is not None and a.Date > startdatetime]
except FileNotFoundError:
    pass

# OK, we have turned the log file into the actions list
# Now analyze the actions list
# We'll create a dictionary of editors with the value bring the accumulators
results: Dict[str, Accumulator]={}  # Key is editor, value is an accumulator
for action in actions:
    if action.Editor not in results.keys():
        results[action.Editor]=Accumulator()
    acc=results[action.Editor]
    acc.Pagecount+=action.Pages
    acc.Bytecount+=action.Bytes
    acc.ConList.Append(action.ConSeries, action.Convention, action.Name)

def IDToName(id: str) -> str:
    convert={
        "conpubs": "Mark Olson",
        "cp-edie": "Edie Stern"
    }
    if id in convert.keys():
        return convert[id]
    return id

# Write reports
with open("Con Series report.txt", "w+") as f:
    for editor, acc in results.items():
        f.writelines("Editor: "+IDToName(editor)+"\n")
        f.writelines("   "+str(acc.ConList.Itemcount)+" items,   "+str(acc.Pagecount)+" pages,   "+"{:,}".format(acc.Bytecount)+" bytes\n")
        f.writelines("Convention series updated: ")
        separator=""
        lst=list(acc.ConList.List.keys())
        lst.sort()
        for conseries in lst:
            f.writelines(separator+conseries)
            separator=", "
        f.writelines("\n\n")


with open("Con Instance report.txt", "w+") as f:
    for editor, acc in results.items():
        f.writelines("Editor: "+IDToName(editor)+"\n")
        f.writelines("   "+str(acc.ConList.Itemcount)+" items,   "+str(acc.Pagecount)+" pages,   "+"{:,}".format(acc.Bytecount)+" bytes\n")
        f.writelines("Conventions updated: ")
        lst=list(acc.ConList.List.keys())
        lst.sort()
        for conseries in lst:
            f.writelines(conseries+": ")
            cons=list(acc.ConList.List[conseries].keys())
            cons.sort()
            separator: str=""
            for con in cons:
                f.writelines(separator+con)
                separator=", "
            f.writelines("\n")
        f.writelines("\n\n")

with open("Con detail report.txt", "w+") as f:
    for editor, acc in results.items():
        f.writelines("Editor: "+IDToName(editor)+"\n")
        f.writelines("   "+str(acc.ConList.Itemcount)+" items,   "+str(acc.Pagecount)+" pages,   "+"{:,}".format(acc.Bytecount)+" bytes\n")
        f.writelines("Conventions updated: ")
        lst=list(acc.ConList.List.keys())
        lst.sort()
        for conseries in lst:
            f.writelines(conseries+": \n")
            cons=list(acc.ConList.List[conseries].keys())
            cons.sort()
            for con in cons:
                f.writelines("   "+con+" -- ")
                separator=""
                for file in acc.ConList.List[conseries][con]:
                    f.writelines(separator+os.path.splitext(file)[0])
                    separator=", "
                f.writelines("\n")
            f.writelines("\n")
        f.writelines("\n\n")

# Write the timestamp
lines=[]
if os.path.exists("Last time.txt"):
    with open("Last time.txt", "r") as f:
        lines=f.readlines()
with open("Last time.txt", "w") as f:
    # Rewrite the file, replacing the date line (if one is present)
    # Basically, we preserve empty lines and lines with '#" is the first non-blank character and replace the first line of any other type with the datetime
    for line in lines:
        line=line.strip()
        if len(line) == 0 or line[0] == "#":
            f.writelines(line+"\n")
            continue
    f.writelines(datetime.now().strftime("%B %d, %Y  %I:%M:%S %p")+"\n")

i=0