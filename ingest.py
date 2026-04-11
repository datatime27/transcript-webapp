#!/usr/bin/env python3
"""
CGI script — populates DB.
"""

import cgitb
cgitb.enable()
from db import *
import MySQLdb

def try_create_user(email, name=None):
    try:
        create_user(email, name)
    except MySQLdb.IntegrityError as e:
        if e.args[0] == 1062:
            print(f"<p>Skipped duplicate: {name}</p>")
        else:
            raise

print("Content-Type: text/html\r\n")

try:
    '''
    version = populate_transcript("transcripts/rwKYWuVluJc.json", "Taskmaster UK", 20, 1)
    try_create_user('datatime27@gmail.com','Peter')
    add_episode_to_user("datatime27@gmail.com", "rwKYWuVluJc")
    
    version = populate_transcript("transcripts/QPxoN8AqoY0.json", "Taskmaster UK", 20, 2)
    add_episode_to_user("datatime27@gmail.com", "QPxoN8AqoY0")

    version = populate_transcript("transcripts/27NM_ZktAeQ.json", "Taskmaster UK", 20, 3)
    version = populate_transcript("transcripts/4f39eGhk2gg.json", "Taskmaster UK", 20, 4)
    version = populate_transcript("transcripts/QbUzce4cajQ.json", "Taskmaster UK", 20, 5)
    version = populate_transcript("transcripts/5dp--alEUwc.json", "Taskmaster UK", 20, 6)
    version = populate_transcript("transcripts/4Mxpg0AgZQ8.json", "Taskmaster UK", 20, 7)
    version = populate_transcript("transcripts/J2RnY2bfCbc.json", "Taskmaster UK", 20, 8)
    version = populate_transcript("transcripts/0FyhuhA_z2c.json", "Taskmaster UK", 20, 9)
    version = populate_transcript("transcripts/7sU7pfZe_6w.json", "Taskmaster UK", 20, 10)
    
    add_episode_to_user("datatime27@gmail.com", "QPxoN8AqoY0")
    add_episode_to_user("datatime27@gmail.com", "27NM_ZktAeQ")
    add_episode_to_user("datatime27@gmail.com", "4f39eGhk2gg")
    add_episode_to_user("datatime27@gmail.com", "QbUzce4cajQ")
    add_episode_to_user("datatime27@gmail.com", "5dp--alEUwc")
    add_episode_to_user("datatime27@gmail.com", "4Mxpg0AgZQ8")
    add_episode_to_user("datatime27@gmail.com", "J2RnY2bfCbc")
    add_episode_to_user("datatime27@gmail.com", "0FyhuhA_z2c")
    add_episode_to_user("datatime27@gmail.com", "7sU7pfZe_6w")
    
    try_create_user('willigese@gmail.com', 'Eleonora')
    try_create_user('grayianalba@gmail.com', 'Alba')
    try_create_user('michelon.leo@gmail.com', 'Leo')

    add_episode_to_user('willigese@gmail.com', 'rwKYWuVluJc')
    add_episode_to_user('grayianalba@gmail.com', 'rwKYWuVluJc')
    add_episode_to_user('michelon.leo@gmail.com', 'rwKYWuVluJc')


    version = populate_transcript("transcripts/09-CXkoQs58.json", "Taskmaster UK", 18, 1)
    add_episode_to_user("datatime27@gmail.com", "09-CXkoQs58")
    
    try_create_user('abbodipro0@gmail.com', 'Abdulwahab Khalil')
    try_create_user('philipvgo97@gmail.com', 'Alan “Soap” Gonzales')
    try_create_user('grayianalba@gmail.com', 'Alba')
    try_create_user('gunaleek@gmail.com', 'Aleek')
    try_create_user('alisonjleonard@gmail.com', 'Alison Leonard')
    try_create_user('alissaalexandra@gmail.com', 'Alissa Alexandra')
    try_create_user('alissawebster12@gmail.com', 'Alissa Webster')
    try_create_user('ted_ned2109@mail.ru', 'Alyona Orlova')
    try_create_user('andreesie@gmail.com', 'Andreas')
    try_create_user('archie.spick@outlook.com', 'Archie')
    try_create_user('atlasblakemore@aol.com', 'Atlas B-H')
    try_create_user('caitprough@gmail.com', 'Cait Prough')
    try_create_user('cazisoffwiththepixi@msn.com', 'Caitlin Guerin')
    try_create_user('cekryan@gmail.com', 'Caitlin Ryan')
    try_create_user('wall.chalice@gmail.com', 'Charles Wallace')
    try_create_user('charlimaguire@icloud.com', 'Charli')
    try_create_user('chrlieonline@gmail.com', 'Charlie (West)')
    try_create_user('chayabrenner11@hotmail.com', 'Chaya Brenner')
    try_create_user('cjwfcjwf@yahoo.com', 'Christine Francis')
    try_create_user('dickjkh@aol.com', 'D. Holbrook')
    try_create_user('davo.mailyan@gmail.com', 'David')
    try_create_user('dominic@userexe.me', 'Dominic')
    try_create_user('willigese@gmail.com', 'Eleonora')
    try_create_user('elliotrmeyer@gmail.com', 'Elliot Meyer')
    try_create_user('elliott.no.yes@gmail.com', 'Elliott')
    try_create_user('fayeanderson@gmx.co.uk', 'Faye Anderson')
    try_create_user('felix.rechberger1@gmx.net', 'Felix')
    try_create_user('hermosillomirandaalex@gmail.com', 'Hania Rangel')
    try_create_user('hannahmcmann94@gmail.com', 'Hannah')
    try_create_user('hrnelson2000@gmail.com', 'Hannah')
    try_create_user('j.kirwann08@gmail.com', 'Jack Kirwan')
    try_create_user('jennifer.a.steel@me.com', 'Jen Steel')
    try_create_user('jenniferteeter503@gmail.com', 'Jen T')
    try_create_user('jessswandale@gmail.com', 'Jess Swandale')
    try_create_user('sixstringstuntman@yahoo.com', 'John Dunn')
    try_create_user('jhynz1306@gmail.com', 'Joyce')
    try_create_user('karligrant5@gmail.com', 'Karli Grant')
    try_create_user('completelyrandon@hotmail.com', 'Kate RC')
    try_create_user('kgardenhayes@gmail.com', 'Katie')
    try_create_user('contactadam222@gmail.com', 'keys')
    try_create_user('kunzarizvii@gmail.com', 'Kunza')
    try_create_user('kylie.mallett@gmail.com', 'Kylie Mallett')
    try_create_user('Lea.meuser@outlook.com', 'Lea Meuser')
    try_create_user('leigh.e.miller@gmail.com', 'Leigh Miller')
    try_create_user('lennartwoste@gmail.com', 'Lennart')
    try_create_user('michelon.leo@gmail.com', 'Leo')
    try_create_user('lisakhelm@gmail.com', 'Lisa H')
    try_create_user('loudavx@gmail.com', 'Lou Davids')
    try_create_user('vallerm2004@gmail.com', 'M. Valler')
    try_create_user('maddie.young274@gmail.com', 'Maddie Ru')
    try_create_user('madeline.ashleigh116@gmail.com', 'Madeline Oxley')
    try_create_user('marjana_grebennikov@gmx.de', 'Mary Jane')
    try_create_user('max.taylor4202@gmail.com', 'Max Taylor')
    try_create_user('dothuymienthao@gmail.com', 'Mien Thao')
    try_create_user('mikael.kalervo.vaananen@gmail.com', 'Mikael')
    try_create_user('nicolechu2727@gmail.com', 'Nicole')
    try_create_user('inesgurtler@gmail.com', 'Nort')
    try_create_user('radhika.gune@gmail.com', 'Radhika')
    try_create_user('rere.rueck@web.de', 'Rebekka')
    try_create_user('blongson@sky.com', 'Red Longson')
    try_create_user('nfreidenreich@gmail.com', 'Ren')
    try_create_user('ceren.selman99@gmail.com', 'ren')
    try_create_user('rtowery23@gmail.com', 'Rob T')
    try_create_user('rorifriedman@gmail.com', 'Rori')
    try_create_user('ryan-mawhinney@hotmail.co.uk', 'Ryan')
    try_create_user('jussi4ever@googlemail.com', 'Sakkiko')
    try_create_user('smgrunig@gmail.com', 'Sarah Grunig')
    try_create_user('sarahemeredith@gmail.com', 'Sarah Meredith')
    try_create_user('sallenworkandmusic@gmail.com', 'Silverley Allen')
    try_create_user('simon.monroe.charbonneau@gmail.com', 'Simon Charbonneau')
    try_create_user('sop.sau97@gmail.com', 'Sophie')
    try_create_user('it.aint.tommy@gmail.com', 'Tabitha Zweck')
    try_create_user('thefourthvine@gmail.com', 'TFV')
    try_create_user('twhavell@gmail.com', 'Thomas Havell')
    try_create_user('tfortony15@gmail.com', 'Tony')
    try_create_user('yukonmild@gmail.com', 'Tracy Erman')
    try_create_user('william.goulden@gmail.com', 'Will G')
    try_create_user('a.tafra33@gmail.com', 'Wren')
    try_create_user('hikari2306@gmail.com', 'YR')
    try_create_user('ghoreishi.tara@gmail.com', None)
    try_create_user('jade.davis0019@gmail.com', None)
    '''
    
    #add_episode_to_user('contactadam222@gmail.com', 'rwKYWuVluJc')
    #add_episode_to_user('yukonmild@gmail.com' , 'rwKYWuVluJc')
    #add_episode_to_user('hannahmcmann94@gmail.com' , 'rwKYWuVluJc')

    #try_create_user('test-user1', 'Other Peter')
    #add_episode_to_user("test-user1", "rwKYWuVluJc")
    
    try_create_user('test-user2', 'Another Peter')
    add_episode_to_user("test-user2", "rwKYWuVluJc")

    print(f"Success")
except Exception as e:
    print(f"<p>Error: {e}</p>")
