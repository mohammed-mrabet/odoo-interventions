"""API JSON consommée par le tableau de bord React.

Authentification par la session Odoo (cookie obtenu via /web/session/authenticate) :
les règles d'accès s'appliquent donc normalement, un technicien ne voit que ses interventions.
"""

from datetime import timedelta

from odoo import fields, http
from odoo.http import request

STATES = ["draft", "planned", "in_progress", "done", "cancel"]
MAX_LIMIT = 200


class InterventionApi(http.Controller):
    @http.route("/api/interventions", type="http", auth="user", methods=["GET"], csrf=False)
    def list_interventions(self, state=None, technician_id=None, limit=50, offset=0, **kwargs):
        domain = []
        if state:
            if state not in STATES:
                return request.make_json_response({"error": f"État inconnu : {state}"}, status=400)
            domain.append(("state", "=", state))
        if technician_id:
            if not str(technician_id).isdigit():
                return request.make_json_response({"error": "technician_id doit être un entier"}, status=400)
            domain.append(("technician_id", "=", int(technician_id)))
        try:
            limit = min(int(limit), MAX_LIMIT)
            offset = max(int(offset), 0)
        except ValueError:
            return request.make_json_response({"error": "limit et offset doivent être des entiers"}, status=400)

        Intervention = request.env["intervention.intervention"]
        records = Intervention.search(domain, limit=limit, offset=offset, order="date_planned desc, id desc")
        return request.make_json_response(
            {"count": Intervention.search_count(domain), "items": [rec._to_api_dict() for rec in records]}
        )

    @http.route("/api/interventions/stats", type="http", auth="user", methods=["GET"], csrf=False)
    def stats(self, **kwargs):
        Intervention = request.env["intervention.intervention"]
        now = fields.Datetime.now()

        by_state = {state: 0 for state in STATES}
        for state, count in Intervention._read_group([], ["state"], ["__count"]):
            by_state[state] = count

        by_type = [
            {"type": t, "label": dict(Intervention._fields["intervention_type"].selection)[t], "count": c}
            for t, c in Intervention._read_group([("state", "!=", "cancel")], ["intervention_type"], ["__count"])
        ]

        technicians = {}
        for tech, state, count in Intervention._read_group(
            [("technician_id", "!=", False), ("state", "!=", "cancel")], ["technician_id", "state"], ["__count"]
        ):
            entry = technicians.setdefault(tech.id, {"id": tech.id, "name": tech.name, "open": 0, "done": 0})
            if state == "done":
                entry["done"] += count
            elif state in ("planned", "in_progress"):
                entry["open"] += count

        done = Intervention.search([("state", "=", "done"), ("duration_real", ">", 0)])
        avg_duration = round(sum(done.mapped("duration_real")) / len(done), 2) if done else 0.0
        # Chiffre d'affaires des interventions terminées sur les 30 derniers jours.
        revenue_30d = sum(Intervention.search([("state", "=", "done"), ("date_end", ">=", now - timedelta(days=30))]).mapped("amount_total"))

        upcoming = Intervention.search(
            [("state", "=", "planned"), ("date_planned", ">=", now), ("date_planned", "<", now + timedelta(days=7))],
            order="date_planned asc",
            limit=10,
        )
        late = Intervention.search([("is_late", "=", True)], order="date_planned asc", limit=10)

        return request.make_json_response(
            {
                "generated_at": fields.Datetime.to_string(now),
                "user": request.env.user.name,
                "currency": request.env.company.currency_id.name,
                "by_state": by_state,
                "by_type": by_type,
                "by_technician": sorted(technicians.values(), key=lambda t: t["open"] + t["done"], reverse=True),
                "late_count": Intervention.search_count([("is_late", "=", True)]),
                "avg_duration_hours": avg_duration,
                "revenue_30d": round(revenue_30d, 2),
                "upcoming": [rec._to_api_dict() for rec in upcoming],
                "late": [rec._to_api_dict() for rec in late],
            }
        )
