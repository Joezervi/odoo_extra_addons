from odoo import models, fields, api
from datetime import datetime, timedelta


class MoDashboard(models.TransientModel):
    """Transient model for MO Dashboard"""
    _name = 'mo.dashboard'
    _description = 'MO Dashboard'

    # Summary Fields
    today_completed = fields.Integer(string="Today's Completed",
        compute='_compute_dashboard_data')
    total_active = fields.Integer(string='Active Orders',
        compute='_compute_dashboard_data')
    overdue_count = fields.Integer(string='Overdue Orders',
        compute='_compute_dashboard_data')
    avg_completion_time = fields.Float(string='Avg Completion Time',
        compute='_compute_dashboard_data')

    # Stage Counts
    count_design = fields.Integer(string='Design',
        compute='_compute_dashboard_data')
    count_printing = fields.Integer(string='Printing',
        compute='_compute_dashboard_data')
    count_finishing = fields.Integer(string='Finishing',
        compute='_compute_dashboard_data')
    count_on_hold = fields.Integer(string='On Hold',
        compute='_compute_dashboard_data')
    count_packing = fields.Integer(string='Packing',
        compute='_compute_dashboard_data')
    count_done = fields.Integer(string='Done',
        compute='_compute_dashboard_data')

    @api.depends('create_date')
    def _compute_dashboard_data(self):
        MrpProduction = self.env['mrp.production']
        today = fields.Date.today()

        for record in self:
            today_start = datetime.combine(today, datetime.min.time())
            today_end = today_start + timedelta(days=1)
            record.today_completed = MrpProduction.search_count([
                ('x_simple_stage', '=', 'done'),
                ('date_finished', '>=', today_start),
                ('date_finished', '<', today_end),
            ])
            record.total_active = MrpProduction.search_count([
                ('x_simple_stage', 'not in', ['done']),
                ('state', '!=', 'cancel'),
            ])
            record.overdue_count = MrpProduction.search_count([
                ('is_overdue', '=', True),
            ])

            thirty_days_ago = today - timedelta(days=30)
            completed_mos = MrpProduction.search([
                ('date_finished', '>=', thirty_days_ago),
                ('x_simple_stage', '=', 'done'),
            ])
            if completed_mos:
                record.avg_completion_time = (
                    sum(mo.total_production_time for mo in completed_mos)
                    / len(completed_mos)
                )
            else:
                record.avg_completion_time = 0

            record.count_design = MrpProduction.search_count([
                ('x_simple_stage', '=', 'design'), ('state', '!=', 'cancel')])
            record.count_printing = MrpProduction.search_count([
                ('x_simple_stage', '=', 'printing'), ('state', '!=', 'cancel')])
            record.count_finishing = MrpProduction.search_count([
                ('x_simple_stage', '=', 'finishing'), ('state', '!=', 'cancel')])
            record.count_on_hold = MrpProduction.search_count([
                ('x_simple_stage', '=', 'on_hold'), ('state', '!=', 'cancel')])
            record.count_packing = MrpProduction.search_count([
                ('x_simple_stage', '=', 'packing'), ('state', '!=', 'cancel')])
            record.count_done = MrpProduction.search_count([
                ('x_simple_stage', '=', 'done'), ('state', '!=', 'cancel')])

    def action_view_kanban(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'MO Kanban Board',
            'res_model': 'mrp.production',
            'view_mode': 'kanban,form',
            'view_id': self.env.ref(
                'bhd_mo_kanban.view_mrp_production_kanban_enhanced').id,
            'context': {'group_by': 'x_simple_stage'},
        }

    def action_view_overdue(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Overdue Manufacturing Orders',
            'res_model': 'mrp.production',
            'view_mode': 'kanban,form,list',
            'domain': [('is_overdue', '=', True)],
            'context': {'group_by': 'x_simple_stage'},
        }

    def action_view_stage_logs(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Stage Transition History',
            'res_model': 'mrp.production.stage.log',
            'view_mode': 'list,form,pivot,graph',
        }

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        return defaults
