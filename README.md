# HackTheBot

<p align="center">
    <img src="https://github.com/user-attachments/assets/17106da1-f82d-4d01-b263-5dc094abb130" width="400">


Here’s a collection of hacked-together scripts to integrate some HTB goodness into your Discord server. These scripts were pieced together to run either on-demand or as services on a server. They use SQLite to keep track of state, so you don't spam duplicate posts every time you run them.

> **Heads Up:** These scripts make heavy use of Discord’s community server features (forum threads). If you don’t want Discord sniffing through your messages (like more than anyways), temporarily enable the community server mode, create a few forums, and then disable it afterward.

---

## Scripts Overview
### htb_machines.py
   - Fetches **unreleased HTB machines** and creates forum threads and announcements.
   - Automatically schedules Discord events for machine releases.
<p align="center">
    <img src="https://github.com/user-attachments/assets/5be698ef-12b8-4b49-8c87-787573497b54" >



### htb_challenges.py
   - Fetches **unreleased HTB challenges** and posts them on Discord.
   - Creates forum threads with appropriate tags (category and difficulty).
   - Posts announcements in a designated channel.
<p align="center">
    <img src="https://github.com/user-attachments/assets/ac95fee3-84c7-418b-b104-6fdfd052ce6e" >
     


### htb_notice.py
   - Grabs platform warnings and notices from HTB, recently some box related credentials were pushed over that endpoint.
<p align="center">
    <img src="https://github.com/user-attachments/assets/11c8052b-173d-4ad4-bfbc-eac71fe44d00" >
  

### htb_osint.py
   - Use `!osint [machine_name]` to fetch machine profiles, creator details, and more.

<p align="center">
    <img src="https://github.com/user-attachments/assets/c78db559-af5b-4bcc-a8df-7109ad350845" >

---


###  Environment Variables
   - Set up a `.env` file in the project directory with the following values:
     ```
     DISCORD_TOKEN=<Your Discord Bot Token>
     HTB_BEARER_TOKEN=<Your HTB API Token>
     GENERAL_CHANNEL_ID=<Channel ID for Announcements>
     FORUM_CHANNEL_ID=<Forum Channel ID for Threads>
     MACHINES_CHANNEL_ID=<Channel ID for Machines Announcements>
     CHALL_VOICE_CHANNEL_ID=<Voice Channel ID for Event Scheduling>
     ```

---


## Permissions Needed

Make sure your Discord bot has these permissions:
- **Send Messages**
- **Manage Threads**
- **Manage Events**
- **View Channels**

---

## SQLite Statefulness

Each script uses SQLite to keep track of already posted challenges, machines, or notices. Databases like `machines.db` and `challenges.db` will be created automatically when you run the scripts.

---

## Final Notes

These scripts are far from perfect and were thrown together to solve a specific set of problems. If you use them and they work, great! If not, feel free to tweak them for your needs.

If something breaks, it’s probably on you (but maybe on me).
