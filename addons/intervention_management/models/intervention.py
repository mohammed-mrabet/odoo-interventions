from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class Intervention(models.Model):
    _name = "intervention.intervention"
    _description = "Intervention"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, date_planned asc, id desc"

    name = fields.Char(string="Référence", required=True, copy=False, readonly=True, default=lambda self: _("Nouvelle"))
    partner_id = fields.Many2one("res.partner", string="Client", required=True, tracking=True)
    address = fields.Char(string="Adresse d'intervention", compute="_compute_address", store=True, readonly=False)
    phone = fields.Char(related="partner_id.phone", string="Téléphone du client")
    technician_id = fields.Many2one("intervention.technician", string="Technicien", tracking=True)
    user_id = fields.Many2one(related="technician_id.user_id", store=True, string="Utilisateur du technicien")
    intervention_type = fields.Selection(
        [
            ("installation", "Installation"),
            ("repair", "Dépannage"),
            ("maintenance", "Maintenance préventive"),
            ("inspection", "Contrôle"),
        ],
        string="Type",
        required=True,
        default="repair",
    )
    priority = fields.Selection(
        [("0", "Normale"), ("1", "Importante"), ("2", "Urgente"), ("3", "Critique")], string="Priorité", default="0"
    )
    description = fields.Html(string="Description du problème")
    report_notes = fields.Html(string="Compte rendu du technicien")

    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("planned", "Planifiée"),
            ("in_progress", "En cours"),
            ("done", "Terminée"),
            ("cancel", "Annulée"),
        ],
        string="État",
        default="draft",
        required=True,
        copy=False,
        tracking=True,
        group_expand="_group_expand_states",
    )

    date_planned = fields.Datetime(string="Date prévue", tracking=True)
    duration_planned = fields.Float(string="Durée prévue (h)", default=2.0)
    date_planned_end = fields.Datetime(string="Fin prévue", compute="_compute_date_planned_end", store=True)
    date_start = fields.Datetime(string="Début réel", copy=False, readonly=True)
    date_end = fields.Datetime(string="Fin réelle", copy=False, readonly=True)
    duration_real = fields.Float(string="Durée réelle (h)", compute="_compute_duration_real", store=True)
    is_late = fields.Boolean(string="En retard", compute="_compute_is_late", search="_search_is_late")

    line_ids = fields.One2many("intervention.line", "intervention_id", string="Matériel utilisé", copy=True)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id, required=True)
    amount_material = fields.Monetary(string="Matériel", compute="_compute_amounts", store=True)
    hourly_rate = fields.Monetary(string="Taux horaire", default=250.0)
    amount_labor = fields.Monetary(string="Main-d'œuvre", compute="_compute_amounts", store=True)
    amount_total = fields.Monetary(string="Total", compute="_compute_amounts", store=True, tracking=True)

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    color = fields.Integer(related="technician_id.color")

    _sql_constraints = [
        ("duration_positive", "CHECK(duration_planned > 0)", "La durée prévue doit être positive."),
        ("name_company_unique", "unique(name, company_id)", "Cette référence d'intervention existe déjà."),
    ]

    # ------------------------------------------------------------------ calculs

    @api.depends("partner_id")
    def _compute_address(self):
        for rec in self:
            p = rec.partner_id
            rec.address = ", ".join(filter(None, [p.street, p.street2, p.zip, p.city])) if p else False

    @api.depends("date_planned", "duration_planned")
    def _compute_date_planned_end(self):
        for rec in self:
            rec.date_planned_end = (
                rec.date_planned + timedelta(hours=rec.duration_planned) if rec.date_planned and rec.duration_planned else False
            )

    @api.depends("date_start", "date_end")
    def _compute_duration_real(self):
        for rec in self:
            if rec.date_start and rec.date_end:
                rec.duration_real = round((rec.date_end - rec.date_start).total_seconds() / 3600, 2)
            else:
                rec.duration_real = 0.0

    @api.depends("line_ids.subtotal", "duration_real", "duration_planned", "hourly_rate", "state")
    def _compute_amounts(self):
        for rec in self:
            rec.amount_material = sum(rec.line_ids.mapped("subtotal"))
            # Main-d'œuvre facturée sur la durée réelle une fois l'intervention terminée, sinon sur la durée prévue.
            hours = rec.duration_real if rec.state == "done" and rec.duration_real else rec.duration_planned
            rec.amount_labor = hours * rec.hourly_rate
            rec.amount_total = rec.amount_material + rec.amount_labor

    def _compute_is_late(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_late = rec.state == "planned" and bool(rec.date_planned) and rec.date_planned < now

    def _search_is_late(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise UserError(_("Opération de recherche non prise en charge."))
        late = [("state", "=", "planned"), ("date_planned", "<", fields.Datetime.now())]
        return late if (operator == "=") == value else ["!", "&", *late]

    @api.model
    def _group_expand_states(self, states, domain, order):
        # Le kanban affiche toutes les colonnes d'état, même vides (sauf « Annulée »).
        return ["draft", "planned", "in_progress", "done"]

    # ---------------------------------------------------------------- contraintes

    @api.constrains("technician_id", "date_planned", "duration_planned", "state")
    def _check_technician_availability(self):
        """Un technicien ne peut pas avoir deux interventions planifiées qui se chevauchent."""
        for rec in self:
            # Seules les interventions réellement planifiées occupent le créneau du technicien.
            if not (rec.technician_id and rec.date_planned) or rec.state not in ("planned", "in_progress"):
                continue
            overlap = self.search(
                [
                    ("id", "!=", rec.id),
                    ("technician_id", "=", rec.technician_id.id),
                    ("state", "in", ("planned", "in_progress")),
                    ("date_planned", "<", rec.date_planned_end),
                    ("date_planned_end", ">", rec.date_planned),
                ],
                limit=1,
            )
            if overlap:
                raise ValidationError(
                    _(
                        "%(tech)s a déjà l'intervention %(ref)s sur ce créneau (%(date)s).",
                        tech=rec.technician_id.name,
                        ref=overlap.name,
                        date=fields.Datetime.to_string(overlap.date_planned),
                    )
                )

    # ------------------------------------------------------------------- création

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nouvelle")) == _("Nouvelle"):
                vals["name"] = self.env["ir.sequence"].next_by_code("intervention.intervention") or _("Nouvelle")
        return super().create(vals_list)

    # ------------------------------------------------------------------- workflow

    def action_plan(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Seule une intervention en brouillon peut être planifiée."))
            if not rec.technician_id or not rec.date_planned:
                raise UserError(_("Indiquez un technicien et une date avant de planifier %s.", rec.name))
        self.write({"state": "planned"})

    def action_start(self):
        if any(rec.state != "planned" for rec in self):
            raise UserError(_("Seule une intervention planifiée peut démarrer."))
        self.write({"state": "in_progress", "date_start": fields.Datetime.now()})

    def action_done(self):
        if any(rec.state != "in_progress" for rec in self):
            raise UserError(_("Seule une intervention en cours peut être terminée."))
        self.write({"state": "done", "date_end": fields.Datetime.now()})

    def action_cancel(self):
        if any(rec.state == "done" for rec in self):
            raise UserError(_("Une intervention terminée ne peut pas être annulée."))
        self.write({"state": "cancel"})

    def action_reset_draft(self):
        self.write({"state": "draft", "date_start": False, "date_end": False})

    def unlink(self):
        if any(rec.state not in ("draft", "cancel") for rec in self):
            raise UserError(_("Seules les interventions en brouillon ou annulées peuvent être supprimées."))
        return super().unlink()

    # ---------------------------------------------------------------- API (tableau de bord)

    def _to_api_dict(self):
        self.ensure_one()
        return {
            "id": self.id,
            "reference": self.name,
            "client": self.partner_id.display_name,
            "technician": self.technician_id.name or None,
            "type": self.intervention_type,
            "type_label": dict(self._fields["intervention_type"].selection)[self.intervention_type],
            "priority": int(self.priority or 0),
            "state": self.state,
            "state_label": dict(self._fields["state"].selection)[self.state],
            "date_planned": fields.Datetime.to_string(self.date_planned) if self.date_planned else None,
            "is_late": self.is_late,
            "duration_planned": self.duration_planned,
            "duration_real": self.duration_real,
            "amount_total": self.amount_total,
            "currency": self.currency_id.name,
        }
