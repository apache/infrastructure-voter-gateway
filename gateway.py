import asfquart
import asfquart.generics
import asfquart.session
import hashlib
import asfpy.sqlite
import quart
import asfpy.syslog
import os
import configparser
"""Voter gateway for the ASF Annual Members Meeting.
This should automagically assign a ballot to new people voting for the first time, 
and keep assigning the same ballot to them if they re-visit the vote site while 
a vote is underway. It will automatically assign a ballot to the last election 
created, so keep that in mind!
"""
STEVE_CONFIG = "/var/www/steve/pysteve/steve.cfg"
# If steve.cfg exists, it will be used to locate the database file.
# Otherwise, it will fall back to the file-path set here:
FALLBACK_DB = "/var/www/steve/steve.db"

# Rewire OAuth to not use OIDC for now
asfquart.generics.OAUTH_URL_INIT = "https://oauth.apache.org/auth?state=%s&redirect_uri=%s"
asfquart.generics.OAUTH_URL_CALLBACK = "https://oauth.apache.org/token?code=%s"

# Print to syslog
lprint = asfpy.syslog.Printer(identity='voter-gateway')


def my_app():
    # Construct the quart service. By default, the oauth gateway is enabled at /oauth.
    app = asfquart.construct("voter_gateway")

    @app.route("/")
    async def get_ballot():
        session = await asfquart.session.read()
        if not session or not session.isMember:
            return quart.redirect("/auth?login=/gateway")

        # Ballot ID: hash of app secret and UID
        uid_hashed = hashlib.sha224((app.secret_key + ":" + session.uid).encode("utf-8")).hexdigest()

        # Check if exists, otherwise add ballot
        ballot_id = await voter_add(session.email, uid_hashed)
        if ballot_id:
            url = f"/election.html?{ballot_id}"
            return quart.redirect(url)
        else:
            return "Could not find the election base data. Please contact Infrastructure!"

    app.runx(port=8085)


async def voter_add(uid, xhash):
    """Add a voter to the election, or returns the ballot ID if it already exists"""
    steve_db = FALLBACK_DB
    # If steve.cfg exists, look in it for where the DB file is
    if os.path.exists(STEVE_CONFIG):
        steve_cfg = configparser.ConfigParser()
        steve_cfg.read(STEVE_CONFIG)
        steve_db = steve_cfg.get("sqlite", "database", fallback=FALLBACK_DB)
    db = asfpy.sqlite.DB(steve_db)
    elections = [x for x in db.fetch("elections", limit=None)]
    if elections:
        # Grab the last (latest) election
        election = elections[-1]
        electionID = elections[-1]['id']
        eid = hashlib.sha512((election["hash"] + xhash).encode("utf-8")).hexdigest()
        if not db.fetchone("voters", id=eid):
            lprint(f"Registered new ballot for:")
            lprint(uid)
            db.insert("voters", {"election": electionID, "hash": xhash, "uid": uid, "id": eid})
        return f"{electionID}/{xhash}"


if __name__ == "__main__":
    my_app()
