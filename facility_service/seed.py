import uuid
import random
from faker import Faker
from sqlalchemy.orm import Session
from app.core.databases import SessionLocal, engine, Base
from .models import Org, Site, Space, SpaceGroup, SpaceGroupMember

# Create tables
Base.metadata.create_all(bind=engine)

fake = Faker()

def safe_json(data):
    """Recursively convert non-serializable values to str/float."""
    if isinstance(data, dict):
        return {k: safe_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [safe_json(v) for v in data]
    elif isinstance(data, (int, float, str, bool)) or data is None:
        return data
    else:
        return str(data)

def seed_data():
    db: Session = SessionLocal()
    try:
        for org_index in range(1, 51):  # 50 orgs
            org = Org(
                id=str(uuid.uuid4()),
                name=f"Org {org_index}",
                legal_name=f"Organization {org_index} Pvt Ltd",
                gst_vat_id=f"GSTIN{1000+org_index}",
                billing_email=f"billing{org_index}@test.org",
                contact_phone=f"+91-900000{org_index:02d}",
                plan=random.choice(["basic", "pro", "enterprise"]),
                locale="en-IN",
                timezone="Asia/Kolkata",
                status="active",
            )
            db.add(org)
            db.flush()  # ensures org.id is available

            for site_index in range(1, 11):  # 10 sites per org
                site = Site(
                    id=str(uuid.uuid4()),
                    org_id=org.id,
                    name=f"Site {site_index} of Org {org_index}",
                    code=f"SITE_{org_index}_{site_index}",
                    kind=random.choice(["residential", "commercial", "mixed-use"]),
                    address=safe_json({
                        "line1": fake.street_address(),
                        "city": fake.city(),
                        "state": fake.state(),
                        "country": "India",
                        "pincode": fake.postcode(),
                    }),
                    geo=safe_json({
                        "lat": float(fake.latitude()),
                        "lng": float(fake.longitude()),
                    }),
                    status=random.choice(["active", "inactive"]),
                )
                db.add(site)
                db.flush()

                spaces_list = []
                for space_index in range(1, 21):  # 20 spaces per site
                    space = Space(
                        id=str(uuid.uuid4()),
                        org_id=org.id,
                        site_id=site.id,
                        code=f"SPACE_{org_index}_{site_index}_{space_index}",
                        name=f"Space {space_index} of Site {site_index}",
                        kind=random.choice(["apartment", "office", "shop", "villa"]),
                        floor=str(random.randint(1, 10)),
                        building_block=f"Block-{random.choice(['A','B','C','D'])}",
                        area_sqft=round(random.uniform(500, 5000), 2),
                        beds=random.randint(1, 5),
                        baths=random.randint(1, 4),
                        attributes=safe_json({
                            "furnished": random.choice([True, False]),
                            "parking": random.choice([True, False]),
                            "balcony": random.choice([True, False]),
                        }),
                        status=random.choice(["available", "occupied", "maintenance"]),
                    )
                    db.add(space)
                    spaces_list.append(space)
                db.flush()

                # Seed Space Groups (2 per site)
                for group_index in range(1, 3):
                    group = SpaceGroup(
                        id=str(uuid.uuid4()),
                        org_id=org.id,
                        site_id=site.id,
                        name=f"Group {group_index} of Site {site_index}",
                        kind=random.choice(["apartment", "office", "shop"]),
                        specs=safe_json({
                            "base_rate": round(random.uniform(1000, 10000), 2),
                            "occupancy": random.randint(1, 5),
                            "amenities": random.sample(["AC", "WiFi", "TV", "Pool", "Parking"], k=3)
                        }),
                    )
                    db.add(group)
                    db.flush()

                    # Add 5 random spaces from this site to the group
                    members = random.sample(spaces_list, k=5)
                    for space in members:
                        member = SpaceGroupMember(
                            group_id=group.id,
                            space_id=space.id
                        )
                        db.add(member)

        db.commit()
        print("✅ Database seeded successfully with orgs, sites, spaces, space groups, and members.")

    except Exception as e:
        db.rollback()
        print("❌ Error seeding data:", e)
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
