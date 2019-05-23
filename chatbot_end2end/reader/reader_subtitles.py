
#!/usr/bin/env python
import os, h5py, re, datetime, sys
from .reader_base import ReaderBase
import xml.etree.ElementTree as ET

'''
    Author: Pengjia Zhu (zhupengjia@gmail.com)
'''

class ReaderSubtitles(ReaderBase):
    '''
        Read from open subtitle, inherit from Reader_Base

        Input:
            - see Reader_Base
    '''

    def __init__(self, **args):
        ReaderBase.__init__(self, **args)

    def _read_xml(self, xml_file):
        tree = ET.parse(xml_file)
        root = tree.getroot()

        max_delta = datetime.timedelta(seconds=1)

        start_time = datetime.datetime.min
        strbuf = ''

        sent_list, strbuf = [], []
        for child in root:
            for elem in child:
                if elem.tag == 'time':
                    elem_id = elem.attrib['id']
                    elem_val = elem.attrib['value'][:-4]
                    if elem_id[-1] == 'S':
                        try:
                            start_time = datetime.datetime.strptime(elem_val, '%H:%M:%S')
                        except:
                            continue
                    else:
                        try:
                            end_time = datetime.datetime.strptime(elem_val, '%H:%M:%S')
                        except:
                            continue
                        sentence = " ".join(strbuf).strip()
                        if sentence[:4] == "****":
                            continue
                        sentence = ReaderBase.clean_text(sentence)
                        if len(sentence) < 1:
                            continue
                        sent_list.append((sentence, start_time, end_time))
                        strbuf = []
                else:
                    try:
                        strbuf.append(elem.text.strip())
                    except:
                        pass

        conv = []
        max_conv_len = 20
        for idx in range(0, len(sent_list) - 1):
            cur = sent_list[idx]
            nxt = sent_list[idx + 1]
            if len(conv) > max_conv_len:
                yield conv[::2]
                yield conv[1::2]
                conv = []
            if nxt[1] - cur[2] <= max_delta and cur and nxt:
                conv.append([cur[0], nxt[0]])
            elif len(conv) > 0:
                #use both side of dialogs
                yield conv[::2]
                if len(conv) > 1:
                    yield conv[1::2]
                conv = []

        if len(conv) > 0 :
            yield conv[::2]
            if len(conv) > 1:
                yield conv[1::2]

    def read(self, filepath):
        cached_data = filepath + '.h5'
        if os.path.exists(cached_data) and os.path.getsize(cached_data) > 102400:
            self.data = h5py.File(cached_data, 'r')
            return

        all_files = []
        def loop_dir(dirpath):
            for f in os.listdir(dirpath):
                fpath = os.path.join(dirpath, f)
                if os.path.isdir(fpath):
                    loop_dir(os.path.join(fpath))
                else:
                    if os.path.splitext(f)[1] == ".xml":
                        all_files.append(fpath)
        loop_dir(filepath)

        def convs_iter(files):
            for f in files:
                for conv in self._read_xml(f):
                    yield conv

        self.data = self.predeal(convs_iter(all_files), cached_data)
