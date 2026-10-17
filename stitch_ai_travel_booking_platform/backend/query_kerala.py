import sqlite3, json

conn = sqlite3.connect("travel.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Kerala is destination_id = 13
did = 13

c.execute("SELECT * FROM website_stays WHERE destination_id=?", (did,))
stays_ws = [dict(r) for r in c.fetchall()]

c.execute("SELECT * FROM stays WHERE destination_id=?", (did,))
stays_all = [dict(r) for r in c.fetchall()]

c.execute("SELECT * FROM experiences WHERE destination_id=?", (did,))
exps = [dict(r) for r in c.fetchall()]

c.execute("SELECT * FROM food_places WHERE destination_id=?", (did,))
food = [dict(r) for r in c.fetchall()]

c.execute("SELECT * FROM holiday_packages WHERE destination_id=?", (did,))
pkgs_raw = [dict(r) for r in c.fetchall()]
pkgs = []
for p in pkgs_raw:
    try:
        p["display"] = json.loads(p["display"])
    except Exception:
        pass
    pkgs.append(p)

c.execute("SELECT * FROM guides WHERE destination_id=?", (did,))
guides = [dict(r) for r in c.fetchall()]

print("website_stays:", len(stays_ws))
print("stays:", len(stays_all))
print("experiences:", len(exps))
print("food_places:", len(food))
print("packages:", len(pkgs))
print("guides:", len(guides))
print(json.dumps({
    "website_stays": stays_ws,
    "stays": stays_all,
    "experiences": exps,
    "food_places": food,
    "packages": pkgs,
    "guides": guides
}, indent=2))

conn.close()
