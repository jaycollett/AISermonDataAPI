import requests
import time
import uuid
import json
import sqlite3
import os

# API Base URL
BASE_URL = "http://localhost:5099"  # Update if running on a different host/port

# Database file
DB_FILE = "sermons.db"

# Generate a random GUID for the sermon
SERMON_GUID = str(uuid.uuid4())

# Sample sermon transcription (Replace this with actual text)
SERMON_TRANSCRIPTION = """
Well, I'm excited to share tonight.  This is a message that's been on my heart for a couple of months now.  So it's been kind of percolating within me for some time.  And it began when, in the reader, we were going through 2 Chronicles,  and something I read one of the days.  As we were going through 2 Chronicles,  and I kind of had just the seed of an idea to share with the church,  but wasn't quite sure when the opportunity would come.  And then I thought about sharing it after the fast, when we had the testimony night.  But I really do like for the church, minus Chad and I, to share on those nights.  I feel like you hear from us the other 51 weeks of the year,  and so it would be good to not share that night.  And so when this opportunity came up to share tonight,  it felt like it was right at home.  So I'm going to talk about 2 Chronicles 14, if you want to turn there.  2 Chronicles 14, chapter 1.  And I want to talk about King Asa.  So you might remember when we were going through the reader  and we were going through 2 Chronicles, what King Asa was like.  He shows up for the first time in 2 Chronicles 14, and it says this.  Abijah slept with his fathers, and they buried him in the city of David.  And Asa, his son, reigned in his place.  In his days, the land had rest for 10 years.  And Asa did what was good and right in the eyes of the Lord his God.  He took away the foreign altars and the high places  and broke down the pillars and cut down the ashram  and commanded Judah to seek the Lord, the God of their fathers,  and to keep the law and the commandment.  He also took out of all the cities of Judah the high places and the incense altars,  and the kingdom had rest under him.  So King Asa does what is right in the eyes of God, and God blesses him.  He's a good king.  It goes on to say, beginning at verse 9,  Zerah the Ethiopian came out against them with an army of a million men and 300 chariots.  A million men.  I really don't think other than where in Scripture it says as many as the sand on the shore,  there's a number as big as a million that's given for the adversaries of Israel.  So an army of a million men and 300 chariots.  And they came as far as Mereshah.  And Asa went out to meet him,  and they drew up their lines of battle in the valley of Zephathah at Mereshah.  And Asa cried to the Lord his God,  O Lord, there is none like you to help between the mighty and the weak.  Help us, O Lord our God, for we rely on you.  And in your name we have come against this multitude, O Lord.  You are our God.  Let not man prevail against you.  So the Lord defeated the Ethiopians before Asa and before Judah,  and the Ethiopians fled.  Asa and the people who were with him pursued them as far as Gerar,  and the Ethiopians fell until none remained alive,  for they were broken before the Lord and his army.  And the men of Judah carried away very much spoil.  So King Asa is vastly outnumbered, and he cries out to God for help.  He trusts in God, and God gives him the victory.  So we've established that Asa does what is right in the eyes of God,  and he trusts God, and God gives him victory.  Asa reigns for 41 years.  He's one of the longest reigning kings in the history of the kings.  And the first 35 years go very well.  But then in chapter 16, we see a change.  It says,  In the thirty-sixth year of the reign of Asa,  Baasha, king of Israel, went up against Judah and built Ramah,  that he might permit no one to go out or come in to Asa, king of Judah.  Then Asa took silver and gold from the treasures of the house of the Lord and the king's house  and sent them to Ben-Hadad, king of Syria, who lived in Damascus, saying,  There is a covenant between me and you, as there was between my father and your father.  Behold, I am sending to you silver and gold.  Go break your covenant with Baasha, king of Israel, that he may withdraw from me.  And Ben-Hadad listened to King Asa and sent the commanders of his armies against the cities of Israel.  And they conquered Aijon, Dan, Abel-Mahim, and all the store cities of Naphtali.  And when Baasha heard of it, he stopped building Ramah and let his work cease.  Then King Asa took all Judah, and they carried away the stones of Ramah and its timber,  with which Baasha had been building.  And with them he built Geba and Mizpah.  At that time, Hanani, the seer, came to Asa, king of Judah, and said to him,  Because you relied on the king of Syria and did not rely on the Lord your God,  the army of the king of Syria has escaped you.  Were not the Ethiopians and the Libyans a huge army with very many chariots and horsemen?  Yet because you relied on the Lord, he gave them into your hand.  For the eyes of the Lord run to and fro throughout the whole earth  to give strong support to those whose heart is blameless toward him.  So when Asa faced a threat, he relied on the king of Syria,  and he didn't rely on the Lord.  Earlier, he had trusted in the Lord, and God gave him help and delivered him.  But here he relies on the king of Syria instead and doesn't rely on the Lord.  And I wonder, where is his prayer from earlier?  Oh, Lord, there is none like you to help.  Where is his courage that leads him forth into battle?  Because he knows that God is with him.  Instead of seeking help from the Lord, he seeks help from the king of Syria.  And when I was reading this a couple of months ago,  I wondered if Asa thought, maybe God will not come through this time.  God's been faithful, but maybe he won't be faithful this time.  God had been faithful to Asa.  He had established him as king.  He had delivered them from the Ethiopians and the Libyans.  But all that was in the past.  It had already happened.  And now he faced a new threat, and he looked for help elsewhere.  And I want to suggest that we are not immune to this.  This is not just something that particularly happened to King Asa.  I think we are not immune to this.  I'm sure that many of us who have been in the family of God for some time  can think of instances of where God came through in a mighty way,  where there was a crisis, there was a real struggle,  and we cried out to God, and God came through in a way that we can only attribute to God.  I'm sure that those of us in the room, many of us can tell stories like that.  And they're wonderful stories, and they're glorious,  and they remind us of God's personal care for our lives.  But, you know, life is not static.  God doesn't solve one problem, and then we never have problems again.  If you've ever seen The Incredibles, at the very beginning, Mr. Incredible says,  no matter how many times you save the world, it always manages to get back in jeopardy again.  Sometimes I just want it to stay saved.  And I think we think the same kind of things about our lives,  but we will deal with problems and situations for the rest of our life.  We'll never be free of those things as we live.  So you have memories of God's help in the past, like Asa did,  and then another crisis or another situation comes up.  And the question is, how will you respond to that?  How will you respond to that?  You know what the playbook says, and you know what play you should run.  So Psalm 50, 15 says,  Call upon me in the day of trouble.  I will deliver you, and you shall glorify me.  1 Peter 5, 7 says,  Cast all your anxiety on him, because he cares for you.  Philippians 4, 6, which Chad preached on just a couple of weeks ago.  Do not be anxious about anything,  but in everything by prayer and supplication with thanksgiving,  let your requests be made known to God.  Common theme in all those scriptures, and I could probably list 20 more,  is to go to God when we're in need of help,  to cry out to God, to lay our troubles at his feet.  We know that we're to seek God's help,  and yet for many of us, there's still a little nagging voice  that says things like,  Maybe God won't come through this time.  Maybe he's sick of me asking for his help all the time.  Maybe he's going to let this difficult thing continue because I don't have my act together,  and it's my fault.  Maybe he just wants to see if I'll be faithful in the midst of trials.  Maybe he'll let me go under,  and all my friends will go on about how this is really good for me.  Maybe I'm on my own this time.  And you know what happens when that voice,  that little nagging voice,  gets louder and louder and louder and loud enough?  You know what happens then?  You start looking for the king of Syria.  You start looking elsewhere, other than God, for help.  Because the last thing you want is to feel like you're on your own.  And you start to hedge your bets.  You hope that God will come through,  but you also want to have some assurance on another front.  You're looking for help elsewhere, too, just in case.  Just in case God doesn't come through in the way that you want him to.  And this can take a lot of different forms.  It could be looking for the next government stimulus to save you financially.  It could be looking to the approval of others to make you feel like you're in.  It could be looking to experts to give us a silver lining to the COVID cloud.  It could be looking to upper management to make sure that your job is secure.  It could be looking for a diagnosis that frees you from taking responsibility for yourself.  It could take a lot of different forms.  But it's all looking to the king of Syria for outside help,  in case God doesn't come through.  And when you look to the king of Syria for help,  what you're really saying is that unless he comes through,  your ship's going to go under.  You're not going to be able to pull out.  And you want reassurance that it's not only God that's on your side.  You want some other kind of assurance, too.  But this is a divided self.  If you want God to be on your side,  but you also want reassurance from somewhere else,  it's a divided self.  Or as James calls it in chapter 1, it's being double-minded.  So James 1,  And maybe that feels familiar to you,  being driven and tossed by the wind and by the waves of the sea.  The truth is that the only way to not be double-minded  is to stand completely upon God,  to stand completely upon God and his help.  That's the only way to keep from being double-minded.  The help that the king of Syria gives comes with a price.  Because if you rely on the help of the king of Syria,  you're just increasingly going to look that way over and over again.  The next crisis that comes,  you're going to look to the king of Syria and so on,  until you barely look to God and expect much from God at all.  Is this good so far?  Psalm 118, 8 and 9 says,  It is better to take refuge in the Lord than to trust in man.  It is better to take refuge in the Lord than to trust in princes.  And Psalm 146 says something similar.  Put not your trust in princes,  in a son of man in whom there is no salvation.  And the Psalms and the rest of Scripture has this,  you know, repeatedly said,  don't put your trust in princes or leaders.  Put your trust in the only one that ultimately can really help.  And that's God.  Let me tell you how this typically goes with me.  Because I always preach to myself first.  I always preach to myself first.  I don't give you anything that's not running through me on some level.  I don't want to be a hypocrite.  And I can't exhort you if I don't also exhort myself.  So let me tell you how this goes with me.  I suddenly face a very challenging situation.  Okay?  Something unexpected.  Something that comes.  And it's something that I don't want to be in.  It's something I don't want to be experiencing.  And there's an initial rush of fear and anxiety.  Okay?  And this is the experience, I think, of David in Psalm 69.  David says,  Save me, O God, for the waters have come up to my neck.  I sink in deep mire where there is no foothold.  All he can do is tread water.  The waters have come up to his neck and he can't find any purchase.  That's how David opens Psalm 69.  Save me, O God.  The waters have come up to my neck.  Now that's the initial experience.  And it's kind of an emotional experience.  It's like, whoa, what's going on?  Within that, I ask God for help.  And I mainly ask God for help with my own reaction to what's going on around me.  I mainly ask for God.  I ask God for help with myself and my own understanding of the situation.  And I say, Father, help me to respond rightly.  Help me to see clearly.  Help me not to collapse within myself.  Does that make sense?  Because really, it's much easier to just give up.  It's much easier to just give up and give in and give in to despair and see the worst of things  and give in to bitterness and just say, I don't expect this to turn out.  I don't expect God to help.  Faith, real faith in God requires some fighting.  It requires fighting on some level.  When praying the Lord's Prayer, when we pray, lead us not into temptation.  When I pray that, I'm thinking at the same time and praying,  Father, please keep us from anything that would so completely overwhelm me  that it would cause me to forget you and to look to the king of Syria for help.  I pray that you would spare me from anything that would just so overwhelm me that I forget you  and I don't look to you for help.  And instead, I look to the king of Syria for help.  So I need God's help with whatever situation is going on.  But I need God's help, especially with my own relationship to it.  Then, when I can get some space, when I can get a little bit of distance,  I pray through writing in my own journal.  Something about writing helps me to think myself clear.  If thoughts are in my head, they just get jumbled around  and I can't always make real clear sense of things.  So sometimes writing things out is a way to think myself clear.  And writing narrows my focus back to God.  It narrows my focus back to God as my real source of help.  I'm reminded of his past and ongoing faithfulness.  And sometimes I'll write about times,  remind myself of times where God has been my source of help in the past.  And I grow in confidence that he will help me this time, too.  I may not know exactly what it looks like,  but I grow in confidence that he will help me on some level  and in some way that I'll know that it's his help.  So if I could graph this, there's the initial moment, the initial crisis,  and then there's the point where I eventually come around and have confidence in God.  And the edge of my maturity, of my growth in God, is shortening that line  to the degree that that line gets smaller and smaller to where there's the crisis.  And then there's the quick turn.  And the acknowledgement that God is with me and that God's going to help.  That, to me, is the edge of me growing in maturity.  And I can tell that I'm growing to know God more and to trust God more  as that line gets shortened.  Is it a whole day?  Is it a couple of hours?  Or even in the midst of the crisis,  can I hear the Holy Spirit speaking to me and saying,  God is with you.  You're going to be all right.  You know, turn this over to him.  Things will be fine.  That's how it goes with me.  And that's a measure of my growth, shortening the line.  And I'm constantly striving to shorten the line.  So I kind of lay that before us, I think, as a challenge.  You know, tomorrow begins another year.  And as I always say, because for some odd reason,  I always end up preaching like the last sermon of the year or the first sermon of the year.  It will not be a new year and a new you.  It will be a new year and it will be the same old you.  It will be the same old me.  That's just the way it works.  But as we go into the new year, let's think about shortening that line  between the crisis and the conviction of faith.  The initial crisis and the inward confidence in our Father.  It will be a work of God when it happens.  It will be a work of God, a work that he produces in us.  But we can start tonight.  We can start right away by turning that over to God, by seeking his help,  asking him for help with ourselves and with our own reaction to what's going on around us.  If you're a Christian and you have the king of Syria's number in your phone,  you need to delete that contact.  In the old days, I would have said if you had the king of Syria on speed dial,  but there is no such thing, I guess, as speed dial anymore.  You need to delete that contact.  And the edge of your spiritual growth may be growing in confidence in your heavenly Father  who loves us perfectly, who provides for us perfectly, who cares for us perfectly.  Our Father, the one in the heavens.  Amen.  As we come to the table, we're going to come to the table.
"""

def initialize_database():
    """Creates the SQLite database and ensures necessary tables exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create sermons table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sermons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sermon_guid TEXT UNIQUE NOT NULL,
            transcription TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            ai_summary TEXT,
            ai_summary_es TEXT,
            bible_books TEXT,
            bible_books_es TEXT,
            created_at TEXT,
            key_quotes TEXT,
            key_quotes_es TEXT,
            sentiment TEXT,
            sentiment_es TEXT,
            sermon_style TEXT,
            sermon_style_es TEXT,
            topics TEXT,
            topics_es TEXT,
            updated_at TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def save_sermon_to_db(sermon_guid, transcription, status="pending"):
    """Saves the sermon details into the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sermons (sermon_guid, transcription, status)
        VALUES (?, ?, ?)
        ON CONFLICT(sermon_guid) DO UPDATE SET 
        status=excluded.status
    """, (sermon_guid, transcription, status))

    conn.commit()
    conn.close()

def update_sermon_details(sermon_data):
    """Updates the sermon with processing results."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE sermons 
        SET status = ?, ai_summary = ?, ai_summary_es = ?, bible_books = ?, 
            bible_books_es = ?, created_at = ?, key_quotes = ?, key_quotes_es = ?, 
            sentiment = ?, sentiment_es = ?, sermon_style = ?, sermon_style_es = ?, 
            topics = ?, topics_es = ?, updated_at = ?
        WHERE sermon_guid = ?
    """, (
        sermon_data.get("status"),
        sermon_data.get("ai_summary"),
        sermon_data.get("ai_summary_es"),
        sermon_data.get("bible_books"),
        sermon_data.get("bible_books_es"),
        sermon_data.get("created_at"),
        sermon_data.get("key_quotes"),
        sermon_data.get("key_quotes_es"),
        sermon_data.get("sentiment"),
        sermon_data.get("sentiment_es"),
        sermon_data.get("sermon_style"),
        sermon_data.get("sermon_style_es"),
        sermon_data.get("topics"),
        sermon_data.get("topics_es"),
        sermon_data.get("updated_at"),
        sermon_data.get("sermon_guid")
    ))

    conn.commit()
    conn.close()

def submit_sermon():
    """Submits a sermon to the API for processing and saves it to the database."""
    url = f"{BASE_URL}/submit_sermon"
    payload = {
        "sermon_guid": SERMON_GUID,
        "transcription": SERMON_TRANSCRIPTION
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 201:
        print(f"✅ Sermon submitted successfully! GUID: {SERMON_GUID}")
        save_sermon_to_db(SERMON_GUID, SERMON_TRANSCRIPTION, status="submitted")
    else:
        print(f"❌ Failed to submit sermon: {response.text}")
    
    return response.json()

def check_status():
    """Checks the status of the sermon processing and updates the database accordingly."""
    url = f"{BASE_URL}/status/{SERMON_GUID}"

    while True:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")

            print(f"📊 Status: {status}")
            if status == "completed":
                print("\n✅ Sermon Processing Completed! Here are the results:\n")
                print(json.dumps(data, indent=4, ensure_ascii=False))
                update_sermon_details(data)
                break
            elif status == "error":
                print("❌ Processing failed!")
                update_sermon_details({"sermon_guid": SERMON_GUID, "status": "error"})
                break
        else:
            print("❌ Error fetching status:", response.text)
            break
        
        print("⏳ Waiting for processing...")
        time.sleep(15)  # Check every 15 seconds

if __name__ == "__main__":
    initialize_database()
    submit_sermon()
    check_status()
