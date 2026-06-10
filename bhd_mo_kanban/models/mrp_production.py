import json
import base64
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

# Stage order for pipeline progress (on_hold is special)
STAGE_ORDER = {
    'design': 1,
    'printing': 2,
    'finishing': 3,
    'packing': 4,
    'qc': 5,
    'done': 6,
    'delivery_done': 7,
    'on_hold': 0,
}

# Stage to Odoo state mapping
STAGE_TO_STATE = {
    'printing': 'progress',
    'finishing': 'progress',
    'packing': 'progress',
    'qc': 'progress',
    'done': 'done',
    'delivery_done': 'done',
}

# Next stage in pipeline
NEXT_STAGE = {
    'design': 'printing',
    'printing': 'finishing',
    'finishing': 'packing',
    'packing': 'qc',
    'qc': 'done',
    'done': 'delivery_done',
}

# Inter-company invoice constants
BHD_COMPANY_ID = 1
CUPSBYAA_COMPANY_ID = 2
BHD_PARTNER_ID = 1           # Bin Haider Darwish S.P.C. partner
CUPSBYAA_PARTNER_ID = 7089   # Cups by AA company partner
BHD_PURCHASE_JOURNAL = 11    # Purchases journal in BHD
CUPSBYAA_SALES_JOURNAL = 30  # Sales journal in Cups by AA
MACHINE_USAGE_RATE = 0.100   # 100 bz per cup - machine usage + blanks
PRINTING_RATE = 0.200        # 200 bz per cup - digital printing
LAMINATION_RATE = 0.050      # 50 bz per cup - lamination


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    # ===== PRIORITY (extend standard) =====
    priority = fields.Selection(selection_add=[
        ('2', 'High'),
        ('3', 'Urgent'),
    ], ondelete={'2': 'set default', '3': 'set default'})

    # ===== KANBAN STAGE =====
    x_simple_stage = fields.Selection([
        ('design', 'Design'),
        ('printing', 'Printing'),
        ('finishing', 'Finishing'),
        ('on_hold', 'On Hold'),
        ('packing', 'Packing'),
        ('qc', 'QC Check'),
        ('done', 'Done'),
        ('delivery_done', 'Delivery Done'),
    ], string='Stage', default='design', tracking=True, index=True,
       group_expand='_group_expand_stage')

    # ===== FEATURE 1: BLOCKED/WAITING STATUS =====
    x_kanban_status = fields.Selection([
        ('normal', 'Normal'),
        ('blocked', 'Blocked'),
        ('waiting', 'Waiting'),
    ], string='Kanban Status', default='normal', tracking=True, index=True,
       help='Normal = in progress, Blocked = cannot proceed, Waiting = waiting for external input')

    # ===== DEADLINE & URGENCY =====
    date_deadline = fields.Date(string='Deadline', tracking=True)
    is_overdue = fields.Boolean(string='Overdue',
        compute='_compute_deadline_info', store=True)
    x_deadline_status = fields.Selection([
        ('none', 'No Deadline'),
        ('ok', 'On Track'),
        ('warning', 'Due Soon'),
        ('danger', 'Overdue'),
        ('today', 'Due Today'),
    ], string='Deadline Status', compute='_compute_deadline_info', store=True)

    # ===== FEATURE 2: DEADLINE DAYS REMAINING =====
    x_deadline_days = fields.Integer(
        string='Days to Deadline',
        compute='_compute_deadline_days',
        store=True,
        help='Positive = days remaining, Negative = days overdue'
    )

    # ===== PRODUCT INFO =====
    x_product_image = fields.Boolean(string="Has Product Image",
        compute="_compute_has_product_image")
    x_has_design_image = fields.Boolean(
        string='Has Design Image',
        compute='_compute_has_design_image',
        help='True if this MO has a design image attachment.'
    )
    x_product_short_name = fields.Char(string='Product Type',
        compute='_compute_product_short_name', store=True)
    x_product_type = fields.Selection(
        related='product_id.type', string='Product Type (System)', store=True)
    x_product_categ_id = fields.Many2one(
        related='product_id.categ_id', string='Product Category', store=True)

    # ===== SALES & CUSTOMER =====
    x_sale_order_id = fields.Many2one('sale.order', string='Sales Order',
        compute='_compute_sale_order', store=True)
    x_partner_id = fields.Many2one('res.partner', string='Customer',
        compute='_compute_sale_order', store=True)
    x_partner_phone = fields.Char(string='Customer Phone',
        compute='_compute_sale_order', store=True)
    x_sale_line_description = fields.Text(string='Sale Description',
        compute='_compute_sale_line_info', store=True)

    # ===== INVOICE PHOTOS =====
    x_invoice_image_ids_json = fields.Char(string='Invoice Image IDs',
        compute='_compute_invoice_images', compute_sudo=True)
    x_invoice_image_count = fields.Integer(string='Invoice Image Count',
        compute='_compute_invoice_images', compute_sudo=True)
    x_invoice_photos_html = fields.Html(string='Invoice Photos',
        compute='_compute_invoice_images', compute_sudo=True, sanitize=False)

    # ===== TIME TRACKING =====
    stage_start_time = fields.Datetime(string='Stage Start Time')
    time_in_stage = fields.Float(string='Time in Current Stage (Hours)',
        compute='_compute_time_in_stage')
    total_production_time = fields.Float(string='Total Production Time (Hours)',
        compute='_compute_total_production_time', store=True)
    time_design = fields.Float(string='Design Time', default=0)
    time_printing = fields.Float(string='Printing Time', default=0)
    time_finishing = fields.Float(string='Finishing Time', default=0)
    time_on_hold = fields.Float(string='On Hold Time', default=0)
    time_packing = fields.Float(string='Packing Time', default=0)
    time_draft = fields.Float(string='Draft Time (Legacy)', default=0)
    time_confirmed = fields.Float(string='Confirmed Time (Legacy)', default=0)
    time_working = fields.Float(string='Working Time (Legacy)', default=0)
    time_paused = fields.Float(string='Paused Time (Legacy)', default=0)

    # ===== PIPELINE PROGRESS =====
    x_stage_index = fields.Integer(string='Stage Index',
        compute='_compute_stage_index')

    # ===== ASSIGNED USER =====
    assigned_to = fields.Many2one('res.users', string='Assigned To',
        domain=lambda self: [('groups_id', 'in', self.env.ref('base.group_user').id)],
        tracking=True)

    # ===== FEATURE 5: WORKER NOTES (enhanced) =====
    x_notes = fields.Text(string='Notes',
        help='Quick notes visible on the kanban card')
    x_notes_updated = fields.Datetime(string='Notes Last Updated', readonly=True)
    x_kanban_notes = fields.Text(string='Kanban Notes',
        related='x_notes', readonly=False,
        help='Alias for x_notes - used by kanban features')

    # ===== KANBAN COLOR (computed) =====
    x_kanban_color = fields.Integer(string='Kanban Color',
        compute='_compute_kanban_color', store=True)
    x_kanban_priority_color = fields.Char(string='Priority Color',
        compute='_compute_priority_color', store=True)

    # ===== NOTIFICATION FLAGS =====
    notification_sent = fields.Boolean(string='Notification Sent', default=False)
    whatsapp_notification_sent = fields.Boolean(string='WhatsApp Sent', default=False)

    # ===== CUPS BY AA INTEGRATION =====
    is_cupsbyaa = fields.Boolean(
        string='Cups by AA Order', default=False, index=True,
        help='True if this MO originated from the Cups by AA website')
    cupsbyaa_order_id = fields.Char(
        string='CupsbyAA Order #', index=True,
        help='Order number from cupsbyaa.com')
    cupsbyaa_order_uuid = fields.Char(
        string='CupsbyAA UUID',
        help='UUID from cupsbyaa orders table')

    # ===== CUPS BY AA EXTENDED FIELDS =====
    cupsbyaa_partner_id = fields.Many2one(
        'res.partner', string='CbAA Customer',
        help='Customer partner for Cups by AA orders (set by sync)')
    cupsbyaa_phone = fields.Char(
        string='CbAA Phone',
        help='Customer phone from cupsbyaa order')
    cupsbyaa_cup_size = fields.Char(
        string='Cup Size',
        help='Cup size from cupsbyaa order (4oz, 8oz, sleeves)')
    cupsbyaa_design_url = fields.Char(
        string='Design File URL',
        help='Original design file URL from cupsbyaa.com')
    cupsbyaa_turnaround = fields.Selection([
        ('normal', 'Normal'),
        ('expedited', 'Expedited'),
        ('urgent', 'Urgent'),
        ('super', 'Super Rush'),
    ], string='Turnaround', default='normal',
        help='Turnaround/urgency level from cupsbyaa order')
    cupsbyaa_multiplier = fields.Float(
        string='Price Multiplier', default=1.0,
        help='Price multiplier for turnaround urgency')
    cupsbyaa_lamination = fields.Boolean(
        string='Has Lamination', default=True,
        help='Whether order includes lamination')
    cupsbyaa_total_price = fields.Float(
        string='Selling Price',
        help='Total selling price from cupsbyaa order')
    cupsbyaa_cost_price = fields.Float(
        string='Cost Price',
        help='Cost price from cupsbyaa order')
    cupsbyaa_customer_remark = fields.Text(
        string='Customer Remark',
        help='Customer remarks/instructions from cupsbyaa order')
    x_design_image = fields.Image(
        string='Design Image',
        max_width=1024,
        max_height=1024,
        attachment=False)
    x_sale_line_design_image = fields.Binary(
        string='Sale Line Design Image',
        compute='_compute_sale_line_design_image',
        store=False,
        help='Design image from the linked sale order line (fallback when x_design_image is empty)')
    cupsbyaa_invoice_created = fields.Boolean(
        string='Invoices Created', default=False,
        help='Whether inter-company invoices have been created for this order')

    # ===== STAGE LOG =====
    stage_log_ids = fields.One2many('mrp.production.stage.log', 'production_id',
        string='Stage History')

    # ==========================================
    # GROUP EXPAND - Show all stages in kanban
    # ==========================================

    @api.model
    def _group_expand_stage(self, stages, domain, order=None):
        return [key for key, val in self._fields['x_simple_stage'].selection]

    # ==========================================
    # COMPUTE METHODS
    # ==========================================

    @api.depends('date_deadline', 'x_simple_stage')
    def _compute_deadline_info(self):
        today = fields.Date.today()
        soon = today + timedelta(days=1)
        for mo in self:
            if mo.x_simple_stage in ('done', 'delivery_done'):
                mo.is_overdue = False
                mo.x_deadline_status = 'ok'
            elif not mo.date_deadline:
                mo.is_overdue = False
                mo.x_deadline_status = 'none'
            elif mo.date_deadline < today:
                mo.is_overdue = True
                mo.x_deadline_status = 'danger'
            elif mo.date_deadline == today:
                mo.is_overdue = False
                mo.x_deadline_status = 'today'
            elif mo.date_deadline <= soon:
                mo.is_overdue = False
                mo.x_deadline_status = 'warning'
            else:
                mo.is_overdue = False
                mo.x_deadline_status = 'ok'

    @api.depends('date_deadline')
    def _compute_deadline_days(self):
        today = fields.Date.today()
        for mo in self:
            if mo.date_deadline:
                mo.x_deadline_days = (mo.date_deadline - today).days
            else:
                mo.x_deadline_days = 0

    @api.depends("product_id")
    def _compute_has_product_image(self):
        tmpl_ids = [mo.product_id.product_tmpl_id.id for mo in self if mo.product_id]
        if tmpl_ids:
            self.env.cr.execute(
                "SELECT id FROM product_template WHERE id = ANY(%s) AND can_image_1024_be_zoomed = TRUE",
                (tmpl_ids,)
            )
            has_img = {row[0] for row in self.env.cr.fetchall()}
        else:
            has_img = set()
        for mo in self:
            tmpl_id = mo.product_id.product_tmpl_id.id if mo.product_id else None
            mo.x_product_image = tmpl_id in has_img

    @api.depends('x_design_image', 'sale_line_id.x_design_image')
    def _compute_has_design_image(self):
        """Check if MO has a design image (own or from sale order line)."""
        for mo in self:
            mo.x_has_design_image = bool(mo.x_design_image) or bool(
                mo.sale_line_id and mo.sale_line_id.x_design_image)

    @api.depends('x_design_image', 'sale_line_id.x_design_image')
    def _compute_sale_line_design_image(self):
        """Get design image: prefer MO's own, fallback to sale order line's."""
        for mo in self:
            if mo.x_design_image:
                mo.x_sale_line_design_image = mo.x_design_image
            elif mo.sale_line_id and mo.sale_line_id.x_design_image:
                mo.x_sale_line_design_image = mo.sale_line_id.x_design_image
            else:
                mo.x_sale_line_design_image = False

    @api.depends('product_id', 'product_id.name')
    def _compute_product_short_name(self):
        for mo in self:
            name = mo.product_id.name or ''
            if name.startswith('[') and ']' in name:
                name = name[name.index(']') + 1:].strip()
            if '(' in name:
                name = name[:name.index('(')].strip()
            mo.x_product_short_name = name or mo.product_id.name or 'Product'

    @api.depends('x_simple_stage')
    def _compute_stage_index(self):
        for mo in self:
            mo.x_stage_index = STAGE_ORDER.get(mo.x_simple_stage, 0)

    @api.depends('origin', 'is_cupsbyaa', 'cupsbyaa_partner_id')
    def _compute_sale_order(self):
        for mo in self:
            if mo.is_cupsbyaa:
                # For cupsbyaa orders, use the dedicated partner fields
                mo.x_sale_order_id = False
                mo.x_partner_id = mo.cupsbyaa_partner_id.id if mo.cupsbyaa_partner_id else False
                mo.x_partner_phone = mo.cupsbyaa_phone or False
                continue
            if mo.origin:
                sale_order = self.env['sale.order'].search(
                    [('name', '=', mo.origin)], limit=1)
                if sale_order:
                    mo.x_sale_order_id = sale_order.id
                    mo.x_partner_id = sale_order.partner_id.id
                    mo.x_partner_phone = sale_order.partner_id.phone
                else:
                    mo.x_sale_order_id = False
                    mo.x_partner_id = False
                    mo.x_partner_phone = False
            else:
                mo.x_sale_order_id = False
                mo.x_partner_id = False
                mo.x_partner_phone = False

    @api.depends('x_sale_order_id', 'product_id')
    def _compute_sale_line_info(self):
        for mo in self:
            if mo.x_sale_order_id and mo.product_id:
                sale_line = mo.x_sale_order_id.order_line.filtered(
                    lambda l: l.product_id == mo.product_id
                )
                mo.x_sale_line_description = sale_line[0].name if sale_line else ''
            else:
                mo.x_sale_line_description = ''

    @api.depends('x_sale_order_id')
    def _compute_invoice_images(self):
        for mo in self:
            if not mo.x_sale_order_id:
                mo.x_invoice_image_ids_json = '[]'
                mo.x_invoice_image_count = 0
                mo.x_invoice_photos_html = ''
                continue
            invoices = mo.x_sale_order_id.invoice_ids
            if not invoices:
                mo.x_invoice_image_ids_json = '[]'
                mo.x_invoice_image_count = 0
                mo.x_invoice_photos_html = ''
                continue
            attachments = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'account.move'),
                ('res_id', 'in', invoices.ids),
                ('mimetype', 'like', 'image/'),
                ('res_field', '=', False),
            ], order='id desc')
            if attachments:
                mo.x_invoice_image_ids_json = json.dumps(attachments.ids)
                mo.x_invoice_image_count = len(attachments)
                imgs = []
                for att in attachments:
                    imgs.append(
                        '<a href="/web/image/%d" target="_blank" '
                        'class="o_mo_photo_thumb">'
                        '<img src="/web/image/%d/200x200" '
                        'alt="%s" loading="lazy"/>'
                        '</a>' % (att.id, att.id, att.name or '')
                    )
                mo.x_invoice_photos_html = (
                    '<div class="o_mo_photos_grid">' +
                    ''.join(imgs) +
                    '</div>'
                )
            else:
                mo.x_invoice_image_ids_json = '[]'
                mo.x_invoice_image_count = 0
                mo.x_invoice_photos_html = ''

    @api.depends('stage_start_time', 'x_simple_stage')
    def _compute_time_in_stage(self):
        now = datetime.now()
        for mo in self:
            if mo.stage_start_time and mo.x_simple_stage not in ['done', 'delivery_done', 'cancel']:
                delta = now - mo.stage_start_time
                mo.time_in_stage = delta.total_seconds() / 3600.0
            else:
                mo.time_in_stage = 0

    @api.depends('time_design', 'time_printing', 'time_finishing', 'time_packing')
    def _compute_total_production_time(self):
        for mo in self:
            mo.total_production_time = (
                mo.time_design + mo.time_printing +
                mo.time_finishing + mo.time_packing
            )

    @api.depends('x_simple_stage', 'is_overdue', 'priority', 'x_kanban_status', 'is_cupsbyaa')
    def _compute_kanban_color(self):
        for mo in self:
            if mo.is_cupsbyaa:
                mo.x_kanban_color = 6
                continue
            if mo.x_kanban_status == 'blocked':
                mo.x_kanban_color = 3
            elif mo.x_kanban_status == 'waiting':
                mo.x_kanban_color = 4
            elif mo.is_overdue:
                mo.x_kanban_color = 9
            elif mo.x_deadline_status == 'today':
                mo.x_kanban_color = 2
            elif mo.priority == '3':
                mo.x_kanban_color = 1
            elif mo.x_simple_stage in ('done', 'delivery_done'):
                mo.x_kanban_color = 10
            elif mo.x_simple_stage == 'printing':
                mo.x_kanban_color = 4
            elif mo.x_simple_stage == 'finishing':
                mo.x_kanban_color = 3
            elif mo.x_simple_stage == 'packing':
                mo.x_kanban_color = 2
            elif mo.x_simple_stage == 'on_hold':
                mo.x_kanban_color = 7
            else:
                mo.x_kanban_color = 0

    @api.depends('priority')
    def _compute_priority_color(self):
        color_map = {
            '0': '#6c757d',
            '1': '#28a745',
            '2': '#ffc107',
            '3': '#dc3545',
        }
        for mo in self:
            mo.x_kanban_priority_color = color_map.get(mo.priority, '#28a745')

    # ==========================================
    # STAGE TRANSITION LOGIC
    # ==========================================

    def _log_stage_transition(self, new_stage):
        self.ensure_one()
        now = fields.Datetime.now()
        time_spent = 0

        if self.stage_start_time and self.x_simple_stage:
            time_spent = (now - self.stage_start_time).total_seconds() / 3600.0

            time_field = 'time_%s' % self.x_simple_stage
            if hasattr(self, time_field):
                current_time = getattr(self, time_field) or 0
                self.with_context(_skip_stage_log=True).write({
                    time_field: current_time + time_spent,
                })

            self.env['mrp.production.stage.log'].sudo().create({
                'production_id': self.id,
                'from_stage': self.x_simple_stage,
                'to_stage': new_stage,
                'duration_hours': time_spent,
                'user_id': self.env.user.id,
            })

        self.with_context(_skip_stage_log=True).write({
            'stage_start_time': now,
        })

    # ==========================================
    # WRITE OVERRIDE - Bidirectional sync
    # ==========================================

    def write(self, vals):
        if self.env.context.get('_skip_stage_log'):
            return super().write(vals)

        # Track notes updates
        if 'x_notes' in vals and vals['x_notes'] != (self[:1].x_notes or ''):
            vals['x_notes_updated'] = fields.Datetime.now()

        if 'x_simple_stage' in vals and len(self) == 1:
            new_stage = vals['x_simple_stage']
            old_stage = self.x_simple_stage
            if new_stage and new_stage != old_stage:
                self._log_stage_transition(new_stage)

                if new_stage in STAGE_TO_STATE and 'state' not in vals:
                    target_state = STAGE_TO_STATE[new_stage]
                    current_order = STAGE_ORDER.get(old_stage, 0)
                    new_order = STAGE_ORDER.get(new_stage, 0)
                    if new_order < current_order and self.state == 'done':
                        vals['state'] = 'progress'
                    elif target_state == 'done' or self.state in ('draft', 'confirmed'):
                        vals['state'] = target_state

                if old_stage == 'design' and new_stage != 'design' and not self.date_start:
                    vals.setdefault('date_start', fields.Datetime.now())

                if new_stage in ('done', 'delivery_done') and not self.date_finished:
                    vals.setdefault('date_finished', fields.Datetime.now())

        elif 'state' in vals and 'x_simple_stage' not in vals:
            new_state = vals['state']
            if new_state == 'done':
                for rec in self.filtered(lambda r: r.x_simple_stage not in ('done', 'delivery_done')):
                    rec._log_stage_transition('done')
                if not any(r.x_simple_stage == 'delivery_done' for r in self):
                    vals['x_simple_stage'] = 'done'
                if not vals.get('date_finished'):
                    vals['date_finished'] = fields.Datetime.now()

        result = super().write(vals)

        if vals.get('x_simple_stage') == 'delivery_done':
            for record in self:
                try:
                    record.action_validate_delivery()
                except Exception:
                    pass

        if vals.get('x_simple_stage') in ('done', 'delivery_done'):
            for record in self:
                record._send_completion_notifications()

        # Cups by AA: sync stage changes back to website DB
        if 'x_simple_stage' in vals:
            for record in self.filtered('is_cupsbyaa'):
                record._sync_cupsbyaa_status(vals['x_simple_stage'])

        # Cups by AA: create inter-company invoices when done
        if vals.get('x_simple_stage') in ('done', 'delivery_done'):
            for record in self.filtered(lambda r: r.is_cupsbyaa and not r.cupsbyaa_invoice_created):
                try:
                    record._create_cupsbyaa_intercompany_invoices()
                except Exception as e:
                    _logger.error('Failed to create invoices for MO %s: %s', record.name, e)

        return result

    # ==========================================
    # ACTION METHODS
    # ==========================================

    def action_next_stage(self):
        self.ensure_one()
        next_stage = NEXT_STAGE.get(self.x_simple_stage)
        if next_stage:
            self.write({'x_simple_stage': next_stage})
        return True

    def action_hold(self):
        self.ensure_one()
        if self.x_simple_stage not in ('done', 'on_hold'):
            self.write({'x_simple_stage': 'on_hold'})
        return True

    def action_resume(self):
        self.ensure_one()
        if self.x_simple_stage == 'on_hold':
            last_log = self.env['mrp.production.stage.log'].search([
                ('production_id', '=', self.id),
                ('to_stage', '=', 'on_hold'),
            ], order='create_date desc', limit=1)
            resume_to = 'printing'
            if last_log and last_log.from_stage not in ('on_hold', 'done'):
                resume_to = last_log.from_stage
            self.write({'x_simple_stage': resume_to})
        return True

    def action_toggle_blocked(self):
        self.ensure_one()
        if self.x_kanban_status == 'normal':
            self.write({'x_kanban_status': 'blocked'})
        else:
            self.write({'x_kanban_status': 'normal'})
        return True

    def action_set_waiting(self):
        self.ensure_one()
        if self.x_kanban_status == 'waiting':
            self.write({'x_kanban_status': 'normal'})
        else:
            self.write({'x_kanban_status': 'waiting'})
        return True

    def action_set_normal(self):
        self.write({'x_kanban_status': 'normal'})
        return True

    def action_open_notes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Notes - %s' % self.name,
            'res_model': 'mrp.production',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('bhd_mo_kanban.view_mrp_production_notes_form').id, 'form')],
            'target': 'new',
            'context': {'dialog_size': 'medium'},
        }

    @api.model
    def action_bulk_move_stage(self, ids, stage):
        valid_stages = [s[0] for s in self._fields['x_simple_stage'].selection]
        if stage not in valid_stages:
            raise UserError('Invalid stage: %s' % stage)
        records = self.browse(ids)
        records.write({'x_simple_stage': stage})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bulk Move Complete',
                'message': 'Moved %d MO(s) to %s.' % (len(records), stage),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def action_bulk_set_blocked(self, ids):
        self.browse(ids).write({'x_kanban_status': 'blocked'})
        return True

    @api.model
    def action_bulk_set_normal(self, ids):
        self.browse(ids).write({'x_kanban_status': 'normal'})
        return True

    @api.model
    def action_bulk_delete(self, ids):
        records = self.browse(ids)
        records.unlink()
        return True

    def action_move_to_printing(self):
        self.ensure_one()
        if self.x_simple_stage == 'design':
            self.write({'x_simple_stage': 'printing'})
        return True

    def action_move_to_finishing(self):
        self.ensure_one()
        if self.x_simple_stage in ('printing', 'on_hold'):
            self.write({'x_simple_stage': 'finishing'})
        return True

    def action_move_to_packing(self):
        self.ensure_one()
        if self.x_simple_stage in ('finishing', 'on_hold'):
            self.write({'x_simple_stage': 'packing'})
        return True

    def action_complete(self):
        self.ensure_one()
        if self.x_simple_stage in ('packing', 'finishing', 'on_hold'):
            self.write({'x_simple_stage': 'done'})
        return True

    def action_deliver(self):
        self.ensure_one()
        if self.x_simple_stage == 'done':
            self.write({'x_simple_stage': 'delivery_done'})
        return True

    def action_reopen(self, target_stage='packing'):
        self.ensure_one()
        self.sudo().with_context(_skip_stage_log=True).write({'state': 'progress'})
        self.write({'x_simple_stage': target_stage})
        return True

    def action_start(self):
        return self.action_move_to_printing()

    def action_pause(self):
        return self.action_hold()

    def action_confirm_mo(self):
        return self.action_move_to_printing()

    # ==========================================
    # NOTIFICATION METHODS
    # ==========================================

    def _send_completion_notifications(self):
        if not self.notification_sent:
            template = self.env.ref(
                'bhd_mo_kanban.email_template_mo_complete',
                raise_if_not_found=False)
            if template:
                try:
                    template.send_mail(self.id, force_send=True)
                    self.with_context(_skip_stage_log=True).write(
                        {'notification_sent': True})
                except Exception as e:
                    _logger.warning('Failed to send MO completion email: %s', e)

        if not self.whatsapp_notification_sent and self.x_partner_phone:
            self._send_whatsapp_notification()

    def _send_whatsapp_notification(self):
        try:
            if self.x_partner_phone:
                self.with_context(_skip_stage_log=True).write(
                    {'whatsapp_notification_sent': True})
        except Exception:
            pass

    # ==========================================
    # CUPS BY AA SYNC METHODS
    # ==========================================

    def _sync_cupsbyaa_status(self, new_stage):
        self.ensure_one()
        if not self.cupsbyaa_order_uuid:
            return

        stage_map = {
            'design': 'received',
            'printing': 'sample_done',
            'finishing': 'production_done',
            'packing': 'production_done',
            'qc': 'production_done',
            'done': 'delivered',
            'delivery_done': 'delivered',
        }

        cupsbyaa_status = stage_map.get(new_stage)
        if not cupsbyaa_status:
            return

        try:
            import subprocess
            cmd = [
                'docker', 'exec', 'cupsbyaa-db',
                'mysql', '-u', 'cupsbyaa', '-pCxnEt4ZAtSFaDN5D', 'cupsbyaa',
                '-e', "UPDATE orders SET production_status='%s' WHERE id='%s'" % (
                    cupsbyaa_status, self.cupsbyaa_order_uuid)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                _logger.info(
                    'CupsbyAA sync: MO %s stage=%s order=%s status=%s',
                    self.name, new_stage, self.cupsbyaa_order_id, cupsbyaa_status)
            else:
                _logger.warning('CupsbyAA sync failed for MO %s: %s', self.name, result.stderr)
        except Exception as e:
            _logger.warning('CupsbyAA sync error for MO %s: %s', self.name, e)

    # ==========================================
    # INTER-COMPANY INVOICE CREATION
    # ==========================================

    def _create_cupsbyaa_intercompany_invoices(self):
        """Create inter-company invoices when a cupsbyaa MO is completed.

        Invoice A: Vendor bill in BHD (Cups by AA charges BHD for machine usage + cups)
        Invoice B: Customer invoice in Cups by AA (BHD charges CbAA for printing services)
        """
        self.ensure_one()
        if not self.is_cupsbyaa or self.cupsbyaa_invoice_created:
            return

        origin_ref = self.origin or ('CUPSBYAA-%s' % self.cupsbyaa_order_id)
        qty = self.product_qty or 1.0

        # Check for existing invoices to avoid duplicates
        existing = self.env['account.move'].sudo().search([
            ('ref', '=', origin_ref),
            ('move_type', 'in', ['in_invoice', 'out_invoice']),
        ], limit=1)
        if existing:
            _logger.info('Invoices already exist for %s, marking as created', origin_ref)
            self.with_context(_skip_stage_log=True).write({'cupsbyaa_invoice_created': True})
            return

        _logger.info('Creating inter-company invoices for MO %s (%s)', self.name, origin_ref)

        # Invoice A: Vendor Bill in BHD
        # Cups by AA invoices BHD for machine usage + blank cups
        try:
            bill_vals = {
                'move_type': 'in_invoice',
                'company_id': BHD_COMPANY_ID,
                'journal_id': BHD_PURCHASE_JOURNAL,
                'partner_id': CUPSBYAA_PARTNER_ID,
                'ref': origin_ref,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': [(0, 0, {
                    'name': 'Machine Usage + Blank Cups - Order #%s (%s)' % (
                        self.cupsbyaa_order_id or '?', self.cupsbyaa_cup_size or 'cups'),
                    'quantity': qty,
                    'price_unit': MACHINE_USAGE_RATE,
                })],
            }
            bill = self.env['account.move'].sudo().with_company(BHD_COMPANY_ID).create(bill_vals)
            _logger.info('Created vendor bill %s (id=%d) in BHD for %s', bill.name, bill.id, origin_ref)
        except Exception as e:
            _logger.error('Failed to create vendor bill for %s: %s', origin_ref, e)

        # Invoice B: Customer Invoice in Cups by AA
        # BHD invoices Cups by AA for printing + lamination + urgency
        try:
            invoice_lines = []

            # Line 1: Digital Printing
            invoice_lines.append((0, 0, {
                'name': 'Digital Printing - Order #%s (%s)' % (
                    self.cupsbyaa_order_id or '?', self.cupsbyaa_cup_size or 'cups'),
                'quantity': qty,
                'price_unit': PRINTING_RATE,
            }))

            # Line 2: Lamination (if applicable)
            if self.cupsbyaa_lamination:
                invoice_lines.append((0, 0, {
                    'name': 'Lamination - Order #%s' % (self.cupsbyaa_order_id or '?'),
                    'quantity': qty,
                    'price_unit': LAMINATION_RATE,
                }))

            # Line 3: Urgency Surcharge (if not normal)
            multiplier = self.cupsbyaa_multiplier or 1.0
            if multiplier > 1.01:  # Not normal
                base_cost = PRINTING_RATE + (LAMINATION_RATE if self.cupsbyaa_lamination else 0)
                surcharge_per_unit = base_cost * (multiplier - 1.0)
                turnaround_label = dict(self._fields['cupsbyaa_turnaround'].selection or {}).get(
                    self.cupsbyaa_turnaround, self.cupsbyaa_turnaround or 'Rush')
                invoice_lines.append((0, 0, {
                    'name': 'Urgency Surcharge (%s, %.0f%%) - Order #%s' % (
                        turnaround_label, (multiplier - 1.0) * 100, self.cupsbyaa_order_id or '?'),
                    'quantity': qty,
                    'price_unit': round(surcharge_per_unit, 3),
                }))

            inv_vals = {
                'move_type': 'out_invoice',
                'company_id': CUPSBYAA_COMPANY_ID,
                'journal_id': CUPSBYAA_SALES_JOURNAL,
                'partner_id': BHD_PARTNER_ID,
                'ref': origin_ref,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': invoice_lines,
            }
            invoice = self.env['account.move'].sudo().with_company(CUPSBYAA_COMPANY_ID).create(inv_vals)
            _logger.info('Created customer invoice %s (id=%d) in CbAA for %s',
                        invoice.name, invoice.id, origin_ref)
        except Exception as e:
            _logger.error('Failed to create customer invoice for %s: %s', origin_ref, e)

        # Mark as created
        self.with_context(_skip_stage_log=True).write({'cupsbyaa_invoice_created': True})

    # ==========================================
    # CRON METHODS
    # ==========================================

    @api.model
    def _cron_refresh_deadline_status(self):
        _logger.info('Refreshing MO deadline statuses...')
        self.env.cr.execute("""
            UPDATE mrp_production
            SET x_deadline_status = CASE
                    WHEN x_simple_stage IN ('done','delivery_done') THEN 'ok'
                    WHEN date_deadline IS NULL THEN 'none'
                    WHEN date_deadline < CURRENT_DATE THEN 'danger'
                    WHEN date_deadline = CURRENT_DATE THEN 'today'
                    WHEN date_deadline <= CURRENT_DATE + INTERVAL '1 day' THEN 'warning'
                    ELSE 'ok'
                END,
                is_overdue = CASE
                    WHEN date_deadline IS NOT NULL
                         AND x_simple_stage NOT IN ('done','delivery_done')
                         AND date_deadline < CURRENT_DATE
                    THEN true
                    ELSE false
                END,
                x_deadline_days = CASE
                    WHEN date_deadline IS NOT NULL
                    THEN (date_deadline - CURRENT_DATE)
                    ELSE 0
                END
            WHERE state != 'cancel'
        """)
        self.env.cr.execute("SELECT COUNT(*) FROM mrp_production WHERE is_overdue = true")
        count = self.env.cr.fetchone()[0]
        _logger.info('Deadline refresh complete. %d overdue MOs.', count)

    @api.model
    def fix_stage_state_sync(self):
        _logger.info('Fixing stage/state sync...')
        fixed = 0
        done_mos = self.search([
            ('state', '=', 'done'),
            ('x_simple_stage', '!=', 'done'),
        ])
        if done_mos:
            done_mos.with_context(_skip_stage_log=True).write({'x_simple_stage': 'done'})
            fixed += len(done_mos)

        progress_mos = self.search([
            ('state', '=', 'progress'),
            ('x_simple_stage', '=', 'design'),
        ])
        if progress_mos:
            progress_mos.with_context(_skip_stage_log=True).write({'x_simple_stage': 'printing'})
            fixed += len(progress_mos)

        no_start = self.search([('stage_start_time', '=', False), ('state', '!=', 'cancel')])
        if no_start:
            no_start.with_context(_skip_stage_log=True).write({'stage_start_time': fields.Datetime.now()})
        return fixed

    # ==========================================
    # DASHBOARD METHODS
    # ==========================================

    @api.model
    def get_dashboard_data(self):
        domain = [('state', '!=', 'cancel')]
        stage_counts = {}
        for stage, label in self._fields['x_simple_stage'].selection:
            count = self.search_count(domain + [('x_simple_stage', '=', stage)])
            stage_counts[stage] = {'label': label, 'count': count}

        today = fields.Date.today()
        today_domain = [
            ('date_finished', '>=', today),
            ('date_finished', '<', today + timedelta(days=1)),
        ]
        today_completed = self.search_count(today_domain)
        overdue_count = self.search_count([('is_overdue', '=', True)])

        thirty_days_ago = today - timedelta(days=30)
        completed_mos = self.search([
            ('date_finished', '>=', thirty_days_ago),
            ('x_simple_stage', '=', 'done'),
        ])
        avg_time = (
            sum(mo.total_production_time for mo in completed_mos) / len(completed_mos)
            if completed_mos else 0
        )

        return {
            'stage_counts': stage_counts,
            'today_completed': today_completed,
            'overdue_count': overdue_count,
            'avg_completion_time': round(avg_time, 2),
            'total_active': self.search_count(domain + [('x_simple_stage', '!=', 'done')]),
        }

    def action_view_stage_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Stage History',
            'res_model': 'mrp.production.stage.log',
            'view_mode': 'list,form',
            'domain': [('production_id', '=', self.id)],
            'context': {'default_production_id': self.id},
        }

    # ==========================================
    # DELIVERY VALIDATION
    # ==========================================

    x_delivery_count = fields.Integer(
        string='Open Deliveries',
        compute='_compute_delivery_info',
        store=False,
    )
    x_has_open_delivery = fields.Boolean(
        string='Has Open Delivery',
        compute='_compute_delivery_info',
        store=False,
    )

    def _compute_delivery_info(self):
        for mo in self:
            pickings = self.env['stock.picking'].search([
                ('origin', 'like', mo.name),
                ('picking_type_code', '=', 'outgoing'),
                ('state', 'in', ['assigned', 'confirmed', 'waiting']),
            ])
            mo.x_delivery_count = len(pickings)
            mo.x_has_open_delivery = len(pickings) > 0

    def action_validate_delivery(self):
        self.ensure_one()
        pickings = self.env['stock.picking'].search([
            ('origin', 'like', self.name),
            ('picking_type_code', '=', 'outgoing'),
            ('state', 'in', ['assigned', 'confirmed', 'waiting']),
        ])
        validated = 0
        for picking in pickings:
            try:
                for move in picking.move_ids.filtered(lambda m: m.state not in ['done', 'cancel']):
                    if move.quantity == 0:
                        move.quantity = move.product_qty
                result = picking.button_validate()
                if isinstance(result, dict) and result.get('res_model'):
                    wizard = self.env[result['res_model']].with_context(
                        result.get('context', {})).create({'pick_ids': [(4, picking.id)]})
                    if hasattr(wizard, 'process'):
                        wizard.process()
                validated += 1
            except Exception as e:
                _logger.warning('Failed to validate picking %s: %s', picking.name, e)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Delivery Validated' if validated else 'Nothing to Validate',
                'message': '%d delivery order(s) validated.' % validated if validated else 'No open deliveries found.',
                'type': 'success' if validated else 'warning',
                'sticky': False,
            }
        }

    def action_view_deliveries(self):
        self.ensure_one()
        pickings = self.env['stock.picking'].search([
            ('origin', 'like', self.name),
            ('picking_type_code', '=', 'outgoing'),
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Deliveries',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', pickings.ids)],
        }
