from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    intervention_ids = fields.One2many("intervention.intervention", "partner_id", string="Interventions")
    intervention_count = fields.Integer(compute="_compute_intervention_count", string="Nombre d'interventions")

    def _compute_intervention_count(self):
        data = self.env["intervention.intervention"]._read_group(
            [("partner_id", "in", self.ids)], ["partner_id"], ["__count"]
        )
        counts = {partner.id: count for partner, count in data}
        for partner in self:
            partner.intervention_count = counts.get(partner.id, 0)

    def action_view_interventions(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("intervention_management.action_intervention")
        action["domain"] = [("partner_id", "=", self.id)]
        action["context"] = {"default_partner_id": self.id}
        return action
