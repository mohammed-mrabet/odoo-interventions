from odoo import api, fields, models


class InterventionTechnician(models.Model):
    _name = "intervention.technician"
    _description = "Technicien"
    _order = "name"

    name = fields.Char(string="Nom", required=True)
    user_id = fields.Many2one(
        "res.users",
        string="Utilisateur Odoo",
        help="Compte utilisé par le technicien pour consulter ses interventions.",
    )
    phone = fields.Char(string="Téléphone")
    email = fields.Char(string="E-mail")
    speciality = fields.Selection(
        [
            ("electricity", "Électricité"),
            ("plumbing", "Plomberie"),
            ("hvac", "Climatisation"),
            ("it", "Informatique"),
            ("maintenance", "Maintenance générale"),
        ],
        string="Spécialité",
        required=True,
        default="maintenance",
    )
    color = fields.Integer(string="Couleur")
    active = fields.Boolean(default=True)
    intervention_ids = fields.One2many("intervention.intervention", "technician_id", string="Interventions")
    intervention_count = fields.Integer(compute="_compute_intervention_stats", string="Nombre d'interventions")
    open_intervention_count = fields.Integer(compute="_compute_intervention_stats", string="Interventions en cours")

    _sql_constraints = [
        ("user_unique", "unique(user_id)", "Ce compte utilisateur est déjà associé à un autre technicien."),
    ]

    @api.depends("intervention_ids.state")
    def _compute_intervention_stats(self):
        # Une seule requête groupée pour tous les techniciens affichés, au lieu d'une par technicien.
        data = self.env["intervention.intervention"]._read_group(
            [("technician_id", "in", self.ids)], ["technician_id", "state"], ["__count"]
        )
        total, open_ = {}, {}
        for technician, state, count in data:
            total[technician.id] = total.get(technician.id, 0) + count
            if state in ("planned", "in_progress"):
                open_[technician.id] = open_.get(technician.id, 0) + count
        for technician in self:
            technician.intervention_count = total.get(technician.id, 0)
            technician.open_intervention_count = open_.get(technician.id, 0)

    def action_view_interventions(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("intervention_management.action_intervention")
        action["domain"] = [("technician_id", "=", self.id)]
        action["context"] = {"default_technician_id": self.id}
        return action
