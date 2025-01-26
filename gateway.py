import asfquart
from asfquart.auth import Requirements as R
import asfquart.generics
import asfquart.session
import hashlib
import asfpy.sqlite
import quart

CURRENT_ELECTION_ID = "45f66648"
STEVE_DB = "/var/www/steve/steve-test.db"


# Rewire OAuth to not use OIDC for now
asfquart.generics.OAUTH_URL_INIT = "https://oauth.apache.org/auth?state=%s&redirect_uri=%s"
asfquart.generics.OAUTH_URL_CALLBACK = "https://oauth.apache.org/token?code=%s"

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
        ballot_id = await voter_add(CURRENT_ELECTION_ID, session.email, uid_hashed)
        url = f"https://vote.apache.org/election.html?{CURRENT_ELECTION_ID}/{ballot_id}"
        return quart.redirect(url)

    app.runx(port=8085)


async def voter_add(election, uid, xhash):
    """Add a voter to the election, or returns the ballot ID if it already exists"""
    db = asfpy.sqlite.DB(STEVE_DB)
    election = db.fetchone("elections", id=election)
    assert election, "Could not find election in db!"
    eid = hashlib.sha512((election['hash'] + uid).encode("utf-8")).hexdigest()
    if not db.fetchone("voters", id=eid):
        db.insert("voters", {"election": election, "hash": xhash, "uid": uid, "id": eid}
        )
    return eid



if __name__ == "__main__":
    my_app()
