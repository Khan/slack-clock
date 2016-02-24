clockbot
========

A slack bot to display a clock, for when your computer's clock just isn't enough.

![Screenshot of ASCII-art clock in a Slack channel](/screenshot.png?raw=true)

Inspired by @mroth's [slacknimate](https://github.com/mroth/slacknimate).

Usage
-----

Due to limitations in Slack, you have to `/invite @your_bot_username` the bot to the channel before using it.  Once that's done, just `/clock [timezone]` to make a new clock.

Deploying
---------
Create a custom slack command, a slack bot user, and a Google App Engine project.  Stick the App Engine project in the Makefile, and the slack command and bot tokens in a file `secrets.py`.  `make deploy`.  KA's instance lives on the app `slack-clock`; ask @benkraft for access.
