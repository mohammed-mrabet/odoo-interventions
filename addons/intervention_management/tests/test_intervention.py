from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestIntervention(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env["res.partner"].create({"name": "Client test", "street": "1 rue Test", "city": "Oujda"})
        cls.tech = cls.env["intervention.technician"].create({"name": "Technicien test", "speciality": "it"})
        cls.tech2 = cls.env["intervention.technician"].create({"name": "Technicien 2", "speciality": "hvac"})
        cls.tomorrow = fields.Datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)

    def _create(self, **vals):
        values = {"partner_id": self.client.id, "intervention_type": "repair"}
        values.update(vals)
        return self.env["intervention.intervention"].create(values)

    def test_reference_sequence_et_adresse(self):
        intervention = self._create()
        self.assertTrue(intervention.name.startswith("INT/"))
        self.assertEqual(intervention.address, "1 rue Test, Oujda")
        self.assertEqual(intervention.state, "draft")

    def test_workflow_complet(self):
        intervention = self._create(technician_id=self.tech.id, date_planned=self.tomorrow)
        intervention.action_plan()
        self.assertEqual(intervention.state, "planned")
        intervention.action_start()
        self.assertEqual(intervention.state, "in_progress")
        self.assertTrue(intervention.date_start)
        intervention.action_done()
        self.assertEqual(intervention.state, "done")
        self.assertTrue(intervention.date_end >= intervention.date_start)

    def test_planification_exige_technicien_et_date(self):
        with self.assertRaises(UserError):
            self._create().action_plan()

    def test_transitions_interdites(self):
        intervention = self._create(technician_id=self.tech.id, date_planned=self.tomorrow)
        with self.assertRaises(UserError):
            intervention.action_done()  # pas encore démarrée
        intervention.action_plan()
        intervention.action_start()
        intervention.action_done()
        with self.assertRaises(UserError):
            intervention.action_cancel()  # déjà terminée

    def test_chevauchement_de_planning_refuse(self):
        first = self._create(technician_id=self.tech.id, date_planned=self.tomorrow, duration_planned=2)
        first.action_plan()
        second = self._create(technician_id=self.tech.id, date_planned=self.tomorrow + timedelta(hours=1))
        with self.assertRaises(ValidationError):
            second.action_plan()

    def test_pas_de_chevauchement_entre_techniciens_differents_ou_creneaux_consecutifs(self):
        self._create(technician_id=self.tech.id, date_planned=self.tomorrow, duration_planned=2).action_plan()
        self._create(technician_id=self.tech2.id, date_planned=self.tomorrow).action_plan()
        self._create(technician_id=self.tech.id, date_planned=self.tomorrow + timedelta(hours=2)).action_plan()

    def test_montants(self):
        intervention = self._create(
            duration_planned=2,
            hourly_rate=250,
            line_ids=[(0, 0, {"name": "Câble", "quantity": 10, "price_unit": 9}), (0, 0, {"name": "Prise", "quantity": 2, "price_unit": 35})],
        )
        self.assertEqual(intervention.amount_material, 160)
        self.assertEqual(intervention.amount_labor, 500)
        self.assertEqual(intervention.amount_total, 660)

    def test_retard_et_recherche(self):
        yesterday = fields.Datetime.now() - timedelta(days=1)
        late = self._create(technician_id=self.tech.id, date_planned=yesterday)
        late.action_plan()
        self.assertTrue(late.is_late)
        self.assertIn(late, self.env["intervention.intervention"].search([("is_late", "=", True)]))
        self.assertNotIn(late, self.env["intervention.intervention"].search([("is_late", "=", False)]))

    def test_suppression_limitee_aux_brouillons(self):
        intervention = self._create(technician_id=self.tech.id, date_planned=self.tomorrow)
        intervention.action_plan()
        with self.assertRaises(UserError):
            intervention.unlink()
        intervention.action_cancel()
        intervention.unlink()

    def test_compteurs(self):
        self._create(technician_id=self.tech.id, date_planned=self.tomorrow).action_plan()
        self._create(technician_id=self.tech.id)
        self.assertEqual(self.tech.intervention_count, 2)
        self.assertEqual(self.tech.open_intervention_count, 1)
        self.assertEqual(self.client.intervention_count, 2)

    def test_technicien_ne_voit_que_ses_interventions(self):
        user = new_test_user(self.env, login="tech_test", groups="intervention_management.group_intervention_technician")
        self.tech.user_id = user
        mine = self._create(technician_id=self.tech.id)
        other = self._create(technician_id=self.tech2.id)
        visible = self.env["intervention.intervention"].with_user(user).search([])
        self.assertIn(mine, visible)
        self.assertNotIn(other, visible)
        with self.assertRaises(AccessError):
            self.env["intervention.intervention"].with_user(user).create({"partner_id": self.client.id})

    def test_rapport_qweb(self):
        intervention = self._create(technician_id=self.tech.id, line_ids=[(0, 0, {"name": "Disjoncteur", "price_unit": 85})])
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "intervention_management.action_report_intervention", intervention.ids
        )
        self.assertIn(intervention.name, html.decode())
        self.assertIn("Disjoncteur", html.decode())
