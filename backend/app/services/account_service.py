"""Contas, propriedade e preferências. Regras de dono ficam aqui (nunca no controller)."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import func, select
from werkzeug.security import check_password_hash, generate_password_hash

from app.errors import AppError
from app.extensions import db
from app.models import Crop, Farm, Planting, User
from app.repositories import catalog_repo
from app.services.location_service import LocationService

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
MIN_PASSWORD = 6


class AccountError(AppError):
    code, status, message = "validation_error", 422, "Dados inválidos."


class InvalidLogin(AppError):
    code, status, message = "invalid_login", 401, "E-mail ou senha não conferem."


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


class AccountService:
    # --- conta -------------------------------------------------------------
    def register(self, name: str, email: str, password: str, consent: bool) -> User:
        name = (name or "").strip()[:60]
        email = _norm_email(email)
        if not name:
            raise AccountError("Diga como podemos te chamar.")
        if not EMAIL_RE.match(email):
            raise AccountError("Esse e-mail não parece válido.")
        if len(password or "") < MIN_PASSWORD:
            raise AccountError(f"A senha precisa ter pelo menos {MIN_PASSWORD} letras ou números.")
        if not consent:
            raise AccountError("Para criar a conta, marque que concorda com o uso dos seus dados.")
        if db.session.scalar(select(func.count()).select_from(User).where(User.email == email)):
            raise AccountError("Já existe uma conta com esse e-mail. Tente entrar.")
        user = User(display_name=name, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return user

    def authenticate(self, email: str, password: str) -> User:
        user = db.session.scalar(select(User).where(User.email == _norm_email(email)))
        # check_password_hash mesmo sem usuário: tempo parecido (não revela se o e-mail existe)
        ok = check_password_hash(user.password_hash if user else generate_password_hash("x"), password or "")
        if not user or not ok:
            raise InvalidLogin()
        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()
        return user

    def change_email(self, user: User, email: str) -> None:
        email = _norm_email(email)
        if not EMAIL_RE.match(email):
            raise AccountError("Esse e-mail não parece válido.")
        taken = db.session.scalar(select(User.id).where(User.email == email, User.id != user.id))
        if taken:
            raise AccountError("Esse e-mail já está em uso.")
        user.email = email
        db.session.commit()

    def update_preferences(self, user: User, *, theme=None, font_size=None, language_level=None, name=None) -> None:
        if theme in ("light", "dark"):
            user.theme = theme
        if font_size in ("normal", "grande", "muito-grande"):
            user.font_size = font_size
        if language_level in ("simple", "standard", "technical"):
            user.language_level = language_level
        if name and name.strip():
            user.display_name = name.strip()[:60]
        db.session.commit()

    def delete(self, user: User) -> None:
        """LGPD: o titular pode apagar a conta. Apaga conta, propriedade e lavouras."""
        db.session.delete(user)
        db.session.commit()

    def export(self, user: User) -> dict:
        """LGPD: o titular pode ver/baixar os próprios dados."""
        farm = user.farm
        return {
            "conta": {"nome": user.display_name, "email": user.email, "criada_em": user.created_at.isoformat(),
                      "preferencias": {"tema": user.theme, "letra": user.font_size, "linguagem": user.language_level}},
            "propriedade": self.farm_view(user) if farm else None,
            "atividades": [{"data": t.on_date.isoformat(), "titulo": t.title, "feita": t.done} for t in user.tasks],
        }

    # --- propriedade ---------------------------------------------------------
    def save_farm(self, user: User, *, place: str, area_ha=None, soil_group=None, crops: list[str] | None = None,
                  name: str | None = None) -> Farm:
        loc = LocationService().resolve(q=place)
        farm = user.farm or Farm(user_id=user.id)
        farm.municipality_ibge = loc.municipality.ibge_code
        farm.name = (name or "").strip()[:80] or None
        try:
            area = float(str(area_ha).replace(",", ".")) if area_ha not in (None, "") else None
        except ValueError:
            raise AccountError("Área inválida.") from None
        if area is not None and not 0 < area < 100_000:
            raise AccountError("Área deve ser um número de hectares maior que zero.")
        farm.area_ha = area
        farm.soil_group = int(soil_group) if str(soil_group or "") in ("1", "2", "3") else None
        db.session.add(farm)
        db.session.flush()
        if crops is not None:
            wanted = {c.id for c in db.session.scalars(select(Crop).where(Crop.slug.in_(crops)))}
            for p in list(farm.plantings):
                if p.crop_id not in wanted:
                    db.session.delete(p)
            have = {p.crop_id for p in farm.plantings}
            for cid in wanted - have:
                db.session.add(Planting(farm_id=farm.id, crop_id=cid))
        db.session.commit()
        return farm

    def farm_view(self, user: User) -> dict | None:
        farm = user.farm
        if farm is None:
            return None
        from app.repositories import territory_repo

        m = territory_repo.get(farm.municipality_ibge)
        crops = [catalog_repo.crop_by_id(p.crop_id) for p in farm.plantings]
        soils = {s["id"]: s["name"] for s in _soil_names()}
        return {
            "name": farm.name,
            "municipality": {"ibge_code": m.ibge_code, "name": m.name, "uf": m.uf},
            "place": f"{m.name} {m.uf}",
            "area_ha": farm.area_ha,
            "soil_group": farm.soil_group,
            "soil_name": soils.get(farm.soil_group, "Não sei"),
            "crops": [{"slug": c.slug, "name": c.official_name} for c in crops if c],
        }


def _soil_names() -> list[dict]:
    from app.services.crop_service import CropService

    return CropService().soils()
