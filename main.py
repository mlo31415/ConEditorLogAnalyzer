from __future__ import annotations
import datetime
from typing import List
import re
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
        self.Size: int=0

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
        m=re.match("Uploaded ConInstance: (.+?):(.+?)\s\[conpubs@fanac.org\s(.+?)]$", line)
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
            action.Size=m.groups()[1]
            action.Pages=m.groups()[2]
        actions.append(action)


# OK, we have turned the log file into the actions list
# Now analyze the actions list
i=0