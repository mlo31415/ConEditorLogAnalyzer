from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
import datetime
from typing import List, Dict
import re
import os
from datetime import datetime

from FTP import FTP
from Log import Log, LogOpen
from HelpersPackage import IsFileWriteable, IsFileReadonly, FormatLink2, SortMessyNumber, Float0, Int0


@dataclass
class Action():
    Date: datetime=None
    _editor: str=""
    ConSeries: str=""
    Convention: str=""
    Name: str=""
    Pages: int=0
    Bytes: int=0

    def IDToName(id: str) -> str:
        convert={
            "conpubs": "Mark Olson",
            "cp-edie": "Edie Stern"
        }
        if id in convert.keys():
            return convert[id]
        return id
    @property
    def Editor(self):
        return self._editor
    @Editor.setter
    def Editor(self, val: str):
        self._editor=val


# Key is con series name; Value is Dict of con instance names.
#       For this Dict, its key is the ConInstance name, its value is a list of files
class Conlist():
    def __init__(self):
        self.List: Dict[str, Dict[str, List[str]]]=defaultdict(lambda: defaultdict(list))
        self.Itemcount: int=0

    def Append(self, Series: str="", Instance: str="", File: str=""):
        if len(Series) > 0 and len(Instance) > 0 and len(File) > 0:
            self.List[Series][Instance].append(File)
            self.Itemcount+=1


@dataclass
class Accumulator():
    #ConList: Conlist=Conlist()
    ConList: Conlist=field(default_factory=Conlist)
    Pagecount: int=0
    Bytecount: int=0


#####################################################################

def main():
    LogOpen("Log -- ConEditorLogAnalyzer.txt", "Log (Errors) -- ConEditorLogAnalyzer.txt")

    f=FTP()

    if not f.OpenConnection("FTP Credentials.json"):
        Log("Main: OpenConnection('FTP Credentials.json' failed")
        exit(0)

    lines: List[str]=FTP().GetFileAsString("", "updatelog.txt").replace("/n", "").split("\n")

    actions: List[Action]=[]

    # The pattern of lines that we care about is
    #       "Uploaded ConInstance: <conseries>;<coninstance> [conpubs@fanac.org <datetime>]
    #   followed by one or more lines which might include this type:
    #       >>add: Source=<name>; Sitename=<name>; Display=<name>; URL=<url>; Size=<num>; Pages=<num>
    isinUpload: bool=False
    conseries: str=""
    coninstance: str=""
    date: datetime=None
    editor: str=""
    for line in lines:
        # When we come across a line that starts "Uploaded ConInstance:", we save the con instance for use in any subsequent actions
        if line.startswith("Uploaded ConInstance: "):
            m=re.match("Uploaded ConInstance: (.+?):(.+?)\s+\[[a-zA-Z\-]+@fanac.org\s+(.+?)]$", line)
            if m is not None:
                conseries=m.groups()[0]
                coninstance=m.groups()[1]
                datetimestring=m.groups()[2].split()
                date=datetime.strptime(" ".join(datetimestring[0:6]), "%A %B %d, %Y  %I:%M:%S %p")
            continue

        if line.startswith("ConEditor starting.   "):
            continue

        if line.startswith("^^deltas by "):
            m=re.match("\^\^deltas by\s+(.+?)@fanac\.org:\s?", line)
            if m is not None:
                editor=m.groups()[0]
            continue

        #----------------------------
        # Take number is bytes or megabytes and yield bytes
        # This is decidedly a heuristic...
        def InterpretSize(num: str, pages: int|None=None)-> int:
            # Is this explicitly a float?  Then it must be in MB. Convert to bytes and return
            if "." in num:
                return int(Float0(num)*1024*1024)

            # It's an integer.
            num=Int0(num)
            # If it's big, it's definitely in bytes
            if num > 200:
                return num
            # Now we have a relatively small number which could be either.  Try to use the page count (if supplied) to decide
            if pages is not None and pages < 3:
                # It might be a small text file a few bytes in size
                # Small page count + small byte count.  Probably it's in bytes
                return num

            # Unknown page count, small size.  Probably MB
            return num*1024*1024    # Small page
        #----------------------------


        if line.startswith(">>add: "):
            action=Action()
            action.ConSeries=conseries
            action.Convention=coninstance
            action.Editor=editor
            action.Date=date
            m=re.match(">>add: Source=.+?; Sitename=.+?; Display=(.+?); URL=.+?; Size=([0-9.]*); Pages=(\d*);", line)
            if m is not None:
                action.Name=m.groups()[0]
                action.Pages=int(m.groups()[2])
                action.Bytes=InterpretSize(m.groups()[1], action.Pages)
                actions.append(action)
                continue
            m=re.match(">>add: Source=.+?; Sitename=.+?; Display=(.+?); Size=([0-9.]*); Pages=(\d*);", line)
            if m is not None:
                action.Name=m.groups()[0]
                action.Pages=int(m.groups()[2])
                action.Bytes=InterpretSize(m.groups()[1], action.Pages)
                actions.append(action)
                continue
            m=re.match(">>add: Source=.+?; Sitename=.+?; Display=(.+?); URL=.+?; Size=([0-9.]);", line)
            if m is not None:
                action.Name=m.groups()[0]
                action.Bytes=InterpretSize(m.groups()[1])
                actions.append(action)
                continue
            m=re.match(">>add: Source=.+?; Sitename=.+?; Display=(.+?); Size=([0-9.]*);", line)
            if m is not None:
                action.Name=m.groups()[0]
                action.Bytes=InterpretSize(m.groups()[1])
                continue
            m=re.match(">>add: Source=.+?; Sitename=.+?; Display=(.+?); Pages=(\d*);", line)
            if m is not None:
                action.Name=m.groups()[0]
                action.Pages=int(m.groups()[1])
                actions.append(action)
                continue
            i=0

    # If we have a "Last time.txt" file, strip out all activity before that time.
    # This file is created at the end of processing, so that the next time ConEditorLogAnalyzer runs, it only lists new stuff.
    startdatetime=datetime(year=2021, month=2, day=3)       # This is the start of the current version of the edit log

    if IsFileReadonly("Last time.txt"):
        Log("\n*** Last time.txt is read-only!\n\n")
    with open("Last time.txt", "r") as f:
        lines=f.readlines()
        lines=[l.strip() for l in lines if len(l.strip()) > 0 and l.strip()[0] != "#"]    # Remove empty lines and lines starting with "#"
    if len(lines) > 0:
        startdatetime=datetime.strptime(lines[0], "%B %d, %Y  %I:%M:%S %p")
        # Remove all actions occuring before startdatetime
        actions=[a for a in actions if a.Date is not None and a.Date > startdatetime]



    # OK, we have turned the log file into the actions list
    # Now analyze the actions list
    # We'll create a dictionary of editors with the value being the accumulators
    resultsByEditor: Dict[str, Accumulator]=defaultdict(Accumulator)  # Key is editor, value is an accumulator
    for action in actions:
        ed=Action.IDToName(action.Editor)
        acc=resultsByEditor[ed]
        acc.Pagecount+=action.Pages
        acc.Bytecount+=action.Bytes
        acc.ConList.Append(action.ConSeries, action.Convention, action.Name)

    # Do a second one with the editors merged
    resultsTotal=Accumulator()
    for action in actions:
        resultsTotal.Pagecount+=action.Pages
        resultsTotal.Bytecount+=action.Bytes
        resultsTotal.ConList.Append(action.ConSeries, action.Convention, action.Name)

    # Write reports
    with open("Con Series report.txt", "w+") as f:
        for editor, acc in resultsByEditor.items():
            f.writelines(startdatetime.strftime("%B %d, %Y")+" -- "+datetime.now().strftime("%B %d, %Y")+"\n\n")
            f.writelines("Editor: "+editor+"\n")
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
        for editor, acc in resultsByEditor.items():
            f.writelines(startdatetime.strftime("%B %d, %Y")+" -- "+datetime.now().strftime("%B %d, %Y")+"\n\n")
            f.writelines("Editor: "+editor+"\n")
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

    # Take names line Boskone 2 and Boskone 11 pad the numbers so they sort numerically
    # We only deal with <name> <num> -- everything else is used as-is
    def ConNameSortKey(s: str) -> str:
        name=s.strip().split(" ")
        if len(name) != 2:
            return s
        val=int(SortMessyNumber(name[1]))
        return f"{name[0]} {val:2}"


    with open("Con detail report.txt", "w+") as f:
        for editor, acc in resultsByEditor.items():
            f.writelines(startdatetime.strftime("%B %d, %Y")+" -- "+datetime.now().strftime("%B %d, %Y")+"\n\n")
            f.writelines("Editor: "+editor+"\n")
            f.writelines("   "+str(acc.ConList.Itemcount)+" items,   "+str(acc.Pagecount)+" pages,   "+"{:,}".format(acc.Bytecount)+" bytes\n")
            f.writelines("Conventions updated: \n")
            lst=list(acc.ConList.List.keys())
            lst.sort()
            for conseries in lst:
                f.writelines(conseries+": \n")
                cons=list(acc.ConList.List[conseries].keys())
                cons.sort(key=lambda x: ConNameSortKey(x))
                for con in cons:
                    f.writelines("   "+con+" -- ")
                    separator=""
                    for file in acc.ConList.List[conseries][con]:
                        f.writelines(separator+os.path.splitext(file)[0])
                        separator=", "
                    f.writelines("\n")
                f.writelines("\n")
            f.writelines("\n\n")

    with open("Con detail report for Edie.txt", "w+") as f:
        f.writelines(startdatetime.strftime("%B %d, %Y")+" -- "+datetime.now().strftime("%B %d, %Y")+"<p><p>\n\n")
        f.writelines("Conpubs: Unless otherwise noted, all scans are by Mark Olson.<br>\n")

        lst=list(resultsTotal.ConList.List.keys())
        def WorldconFirst(e) -> bool:
            return e if e != "Worldcon" else " "
        lst.sort(key=WorldconFirst)

        def IsSandbox(con: str) -> bool:
            return con.lower().startswith("xx") or con.lower().startswith("yy") or con.lower().startswith("zz")

        def WriteFileList(files, added, f):
            f.writelines(f"---{added} added ")
            separator=""
            for file in files:
                f.writelines(separator+os.path.splitext(file)[0])
                separator=", "
            f.writelines("<br>\n")

        # Output structure:
        #   ---Conseries
        #       Con 'added' list of items
        # There's special code to merge the Conseries to the con when we only added material for a single con in that series
        # When a conseries is present, it is a link to the con series index page.  When it's a single con, there is a link to that con's page
        for conseries in lst:
            if IsSandbox(conseries):      # Skip since these are the testing sandboxes
                continue

            cons=list(resultsTotal.ConList.List[conseries].keys())

            if len(cons) == 1:
                # Special case when there is only one con in the list for this con series
                con=cons[0]
                added=FormatLink2(f"fanac.org/conpubs/{conseries}/{con}", con)
                WriteFileList(resultsTotal.ConList.List[conseries][con], added, f)
            else:
                link=FormatLink2(f"fanac.org/conpubs/{conseries}", conseries)
                f.writelines(f"--{link}:<br>\n")

                cons.sort(key=lambda x: ConNameSortKey(x))
                for con in cons:
                    WriteFileList(resultsTotal.ConList.List[conseries][con], con, f)
            f.writelines("<br>\n")
        f.writelines("\n")

    # If the file is writeable, write the timestamp
    # (The file is commonly set to read-only during debugging.)
    lines=[]
    if os.path.exists("Last time.txt"):
        with open("Last time.txt", "r") as f:
            lines=f.readlines()

    if IsFileWriteable("Last time.txt"):
        with open("Last time.txt", "w") as f:
            # Rewrite the file, replacing the date line (if one is present)
            # Basically, we preserve empty lines and lines with '#" is the first non-blank character and replace the first line of any other type with the datetime
            for line in lines:
                line=line.strip()
                if len(line) == 0 or line[0] == "#":
                    f.writelines(line+"\n")
                    continue
            f.writelines(datetime.now().strftime("%B %d, %Y  %I:%M:%S %p")+"\n")



if __name__ == "__main__":
    main()