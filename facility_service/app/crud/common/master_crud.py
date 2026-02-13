from sqlalchemy.orm import Session
from ...models.space_sites.accessories import Accessory


def get_accessories(db: Session):
    accessories = db.query(Accessory).order_by(Accessory.name).all()
    return [
        {
            "id": str(a.id),
            "name": a.name
        }
        for a in accessories
    ]
