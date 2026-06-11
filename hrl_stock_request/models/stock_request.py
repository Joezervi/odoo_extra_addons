from datetime import date, datetime, time, timedelta

from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrlStockRequest(models.Model):
    _name = "hrl.stock.request"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "name"
    _order = "name desc"
    _description = "Stock Request"

    name = fields.Char(string="Request Number")
    state = fields.Selection([
        ('draft','Draft'),
        ('confirm','Confirm'),
        ('validate','Validate'),
        ('cancel','Canceled')
    ], string="Status", default="draft", tracking=True)
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company, readonly=True)
    warehouse_id = fields.Many2one(comodel_name="stock.warehouse", string="Warehouse", required=True, tracking=True)
    picking_type_id = fields.Many2one(comodel_name="stock.picking.type", string="Source Operation Type", required=True, tracking=True)
    location_id = fields.Many2one(comodel_name="stock.location", string="Source Location", required=True, tracking=True)
    location_dest_id = fields.Many2one(comodel_name="stock.location", string="Destination Location", required=True, tracking=True)
    warehouse_dest_id = fields.Many2one(comodel_name="stock.warehouse", related="location_dest_id.warehouse_id", string="Warehouse", store=True)
    picking_type_dest_id = fields.Many2one(comodel_name="stock.picking.type", string="Dest Operation Type", required=True, tracking=True)
    request_uid = fields.Many2one(comodel_name="res.users", string="Request By", default=lambda self: self.env.user, readonly=True)
    request_date = fields.Date(string="Request Date", default=lambda self: fields.Date.context_today(self), readonly=True)
    scheduled_date = fields.Datetime(string="Scheduled Date", default=fields.Datetime.now, required=True)
    notes = fields.Text(string="Notes")
    line_ids = fields.One2many(comodel_name="hrl.stock.request.line", inverse_name="request_id", string="Request List")
    picking_ids = fields.One2many(comodel_name="stock.picking", inverse_name="stock_request_id", string="Operations")
    outgoing_count = fields.Integer('Delivery', compute="_compute_transfer_count")
    incoming_count = fields.Integer('Receipt', compute="_compute_transfer_count")

    def get_sequence(self, name=False, obj=False, pref=False, company_id=False):
        sequence_id = self.env['ir.sequence'].sudo().search([
            ('name', '=', name),
            ('code', '=', obj),
            ('prefix', '=', pref),
            ('company_id','=', company_id)
        ])
        if not sequence_id:
            sequence_id = self.env['ir.sequence'].sudo().create({
                'name': name,
                'code': obj,
                'company_id': company_id,
                'implementation': 'no_gap',
                'prefix': pref,
                'padding': 5
            })
            
        return sequence_id.sudo().next_by_id()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')):
                company_id = self.env['res.company'].sudo().browse(vals.get('company_id', self.company_id))
                vals['name'] = self.with_company(company_id).get_sequence('HrlStockRequest', 'hrl.stock.request', 'SR/', company_id.id)
        return super(HrlStockRequest, self).create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_cancelled(self):
        for rec in self:
            if not rec.state == 'cancel':
                raise UserError(_('To delete a stock request, you must cancel it first !'))

    @api.onchange('warehouse_id')
    def _onchange_warehouse(self):
        for rec in self:
            if rec.warehouse_id:
                rec.location_id = rec.warehouse_id.lot_stock_id.id
            else:
                rec.location_id = False

    def button_confirm(self):
        self.ensure_one()

        if not self.line_ids:
            raise ValidationError(_("Request List cannot be empty!\nPlease add products to the request."))

        self.state = 'confirm'

    def button_validate(self):
        self.ensure_one()

        if not self.line_ids:
            raise ValidationError(_("Request List cannot be empty!\nPlease add products to the request."))

        location_transit_id = self.env['stock.location'].search([
            ('usage', '=', 'transit'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not location_transit_id:
            raise ValidationError(_("Transit Location for Company '%s' is not found!\n"
                                  "Please configure a Transit location in Inventory > Configuration > Locations.") % self.company_id.name)

        outgoing_picking_type_id = self.picking_type_id
        incoming_picking_type_id = self.picking_type_dest_id

        if not outgoing_picking_type_id:
            raise ValidationError(_("Operations Type 'Internal Transfer' for Warehouse '%s' is not found!\n"
                                  "Please check warehouse configuration.") % self.location_id.warehouse_id.name)
        
        if not incoming_picking_type_id:
            raise ValidationError(_("Operations Type 'Internal Transfer' for Warehouse '%s' is not found!\n" 
                                  "Please check warehouse configuration.") % self.location_dest_id.warehouse_id.name)

        outgoing_move_vals = []
        for line in self.line_ids:
            outgoing_move_vals.append((0,0,{
                'stock_request_line_id' : line.id,
                'product_id'            : line.product_id.id,
                'product_uom_qty'       : line.product_qty,
                'product_uom'           : line.product_uom_id.id,
                # 'name'                  : line.name,
                'company_id'            : outgoing_picking_type_id.company_id.id,
                'date_deadline'         : self.scheduled_date,
                'date'                  : self.scheduled_date,
                'location_id'           : self.location_id.id,
                'location_dest_id'      : location_transit_id.id,
                'picking_type_id'       : outgoing_picking_type_id.id, 
            }))

        outgoing_picking_id = self.env['stock.picking'].create({
            'stock_request_id'          : self.id,
            'scheduled_date'            : self.scheduled_date,
            'origin'                    : self.name,
            'company_id'                : outgoing_picking_type_id.company_id.id,
            'picking_type_id'           : outgoing_picking_type_id.id,
            'location_id'               : self.location_id.id,
            'location_dest_id'          : location_transit_id.id,
            'move_ids'  : outgoing_move_vals
        })
        outgoing_picking_id.action_confirm()

        incoming_move_vals = []
        for line in self.line_ids:
            incoming_move_vals.append((0,0,{
                'stock_request_line_id' : line.id,
                'product_id'            : line.product_id.id,
                'product_uom_qty'       : line.product_qty,
                'product_uom'           : line.product_uom_id.id,
                # 'name'                  : line.name,
                'company_id'            : incoming_picking_type_id.company_id.id,
                'date_deadline'         : self.scheduled_date,
                'date'                  : self.scheduled_date,
                'location_id'           : location_transit_id.id,
                'location_dest_id'      : self.location_dest_id.id,
                'picking_type_id'       : incoming_picking_type_id.id, 
            }))

        incoming_picking_id = self.env['stock.picking'].create({
            'stock_request_id'          : self.id,
            'scheduled_date'            : self.scheduled_date,
            'origin'                    : self.name,
            'company_id'                : incoming_picking_type_id.company_id.id,
            'picking_type_id'           : incoming_picking_type_id.id,
            'location_id'               : location_transit_id.id,
            'location_dest_id'          : self.location_dest_id.id,
            'move_ids'                  : incoming_move_vals
        })
        incoming_picking_id.action_confirm()

        self.state = 'validate'

    def button_cancel(self):
        self.ensure_one()

        self.state = 'cancel'

    def button_draft(self):
        self.ensure_one()

        self.state = 'draft'

    def _compute_transfer_count(self):
        for rec in self:
            rec.outgoing_count = len(rec.picking_ids.filtered(lambda p: p.location_id.id == rec.location_id.id))
            rec.incoming_count = len(rec.picking_ids.filtered(lambda p: p.location_dest_id.id == rec.location_dest_id.id))

    def action_view_outgoing(self):
        self.ensure_one()

        action = self.env.ref('stock.action_picking_tree_all').sudo().read()[0]
        action['domain'] = [('stock_request_id','=', self.id),('location_id','=', self.location_id.id)]
        return action

    def action_view_incoming(self):
        self.ensure_one()

        action = self.env.ref('stock.action_picking_tree_all').sudo().read()[0]
        action['domain'] = [('stock_request_id','=', self.id),('location_dest_id','=', self.location_dest_id.id)]
        return action

class HrlStockRequestLine(models.Model):
    _name = "hrl.stock.request.line"
    _rec_name = "product_id"
    _description = "Stock Request List"

    request_id = fields.Many2one(comodel_name="hrl.stock.request", string="Request")
    product_id = fields.Many2one(comodel_name="product.product", string="Product", required=True)
    name = fields.Char('Description')
    product_uom_id = fields.Many2one(comodel_name="uom.uom", string="UoM", required=True)
    product_qty = fields.Float(string="Quantity", digits='Product Unit of Measure', default=1.0)

    @api.constrains('product_qty')
    def _check_quantity(self):
        for rec in self:
            if rec.product_qty <= 0:
                raise ValidationError(_("Product quantity must be greater than zero!"))

    @api.onchange("product_id")
    def _onchange_product(self):
        for rec in self:
            if rec.product_id:
                rec.product_uom_id = rec.product_id.uom_id.id
                rec.name = rec.product_id.display_name