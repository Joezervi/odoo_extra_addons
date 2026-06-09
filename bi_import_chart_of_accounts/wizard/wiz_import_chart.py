# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import tempfile
import binascii
from odoo.exceptions import UserError
from odoo import models, fields, exceptions, api, _
import logging
_logger = logging.getLogger(__name__)
import io
try:
    import xlrd
except ImportError:
    _logger.debug('Cannot `import xlrd`.')
try:
    import csv
except ImportError:
    _logger.debug('Cannot `import csv`.')
try:
    import xlwt
except ImportError:
    _logger.debug('Cannot `import xlwt`.')
try:
    import cStringIO
except ImportError:
    _logger.debug('Cannot `import cStringIO`.')
try:
    import base64
except ImportError:
    _logger.debug('Cannot `import base64`.')

ACCOUNT_TYPE_MAP = {
    "Receivable": "asset_receivable",
    "Bank and Cash": "asset_cash",
    "Current Assets": "asset_current",
    "Non-current Assets": "asset_non_current",
    "Prepayments": "asset_prepayments",
    "Fixed Assets": "asset_fixed",
    "Payable": "liability_payable",
    "Credit Card": "liability_credit_card",
    "Current Liabilities": "liability_current",
    "Non-current Liabilities": "liability_non_current",
    "Equity": "equity",
    "Current Year Earnings": "equity_unaffected",
    "Income": "income",
    "Other Income": "income_other",
    "Expenses": "expense",
    "Other Expenses": "expense_other",
    "Depreciation": "expense_depreciation",
    "Cost of Revenue": "expense_direct_cost",
    "Off-Balance Sheet": "off_balance",
}


class InheritAccountaccount(models.Model):
    _inherit = "account.account"

    is_import = fields.Boolean(string="imported data", default=False)

class ImportChartAccount(models.TransientModel):
    _name = "import.chart.account"
    _description = "Chart of Account"

    File_slect = fields.Binary(string="Select Excel File")
    file_name = fields.Char('filename', size=64)

    import_option = fields.Selection([('csv', 'CSV File'),('xls', 'XLS File')],string='Select',default='csv')

    
    def imoport_file(self):
        if self.import_option == 'csv':
            keys = ['code', 'name', 'user_type_id']

            try:
                csv_data = base64.b64decode(self.File_slect)
                data_file = io.StringIO(csv_data.decode("utf-8"))
                data_file.seek(0)
                file_reader = []
                values = {}
                csv_reader = csv.reader(data_file, delimiter=',')
                file_reader.extend(csv_reader)

            except:

                raise UserError(_("Invalid file!"))

            for i in range(len(file_reader)):
                field = list(map(str, file_reader[i]))

                if i == 0:
                    continue

                field += [''] * (9 - len(field))

                values = {
                    'code': field[0] or '',
                    'name': field[1] or '',
                    'user': field[2] or '',
                    'tax': field[3] or '',
                    'tag': field[4] or '',
                    'group': field[5] or '',
                    'currency': field[6] or '',
                    'reconcile': field[7] or '',
                    'deprecat': field[8] or '',
                }

                if not values['code'] or not values['name'] or not values['user']:
                    raise UserError(_(
                        "Missing required fields in XLS file!\n"
                        "Row %s → Code, Name, and Account Type are mandatory.\n"
                        "Problematic Row: %s" % (i + 1, field)
                    ))

                res = self.create_chart_accounts(values)

# ---------------------------------------
        elif self.import_option == 'xls':
            try:
                fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
                fp.write(binascii.a2b_base64(self.File_slect))
                fp.seek(0)
                values = {}
                workbook = xlrd.open_workbook(fp.name)
                sheet = workbook.sheet_by_index(0)

            except:
                raise UserError(_("Invalid file!"))

            for row_no in range(sheet.nrows):
                if row_no <= 0:
                    continue

                line = list(map(lambda row: isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value),
                                sheet.row(row_no)))

                line += [''] * (9 - len(line))

                values = {
                    'code': line[0] or '',
                    'name': line[1] or '',
                    'user': line[2] or '',
                    'tax': line[3] or '',
                    'tag': line[4] or '',
                    'group': line[5] or '',
                    'currency': line[6] or '',
                    'reconcile': line[7] or '',
                    'deprecat': line[8] or '',
                }

                if not values['code'] or not values['name'] or not values['user']:
                    raise UserError(_(
                        "Missing required fields in CSV file!\n"
                        "Row %s → Code, Name, and Account Type are mandatory.\n"
                        "Problematic Row: %s" % (row_no + 1, line)
                    ))

                res = self.create_chart_accounts(values)
# ------------------------------------------------------------                      
        else:
            raise UserError(_("Please select any one from xls or csv formate!"))

        return res
    
    def create_chart_accounts(self, values):
        if not values.get("code"):
            raise UserError(_("Code field cannot be empty."))

        if not values.get("name"):
            raise UserError(_("Name field cannot be empty."))

        if not values.get("user"):
            raise UserError(_("Type field cannot be empty."))

        s = str(values.get("code"))
        code_no = s.rstrip("0").rstrip(".") if "." in s else s

        user_value = values.get("user").strip()
        account_type = ACCOUNT_TYPE_MAP.get(user_value)
        if not account_type:
            raise UserError(_("%s Account Type is not in your system") % user_value)

        account_obj = self.env["account.account"]
        account_search = account_obj.search([("account_type", "=", account_type)], limit=1)
        if not account_search:
            raise UserError(_("No account found with type: %s") % account_type)
        is_reconcile = str(values.get("reconcile")).upper() in ["TRUE", "1", "YES"]
        is_deprecated = str(values.get("deprecat")).upper() in ["TRUE", "1", "YES"]
        currency_get = self.find_currency(values.get("currency"))
        group_get = self.find_group(values.get("group"))

        tax_ids = []
        if values.get("tax"):
            tax_names = [x.strip() for x in values.get("tax").split(",")]
            for tax_name in tax_names:
                tax = self.env["account.tax"].search([("name", "=", tax_name)], limit=1)
                if not tax:
                    raise UserError(_("Tax '%s' is not found in the system.") % tax_name)
                tax_ids.append(tax.id)

        tag_ids = []
        if values.get("tag"):
            tag_names = [x.strip() for x in values.get("tag").split(",")]
            for tag_name in tag_names:
                tag = self.env["account.account.tag"].search([("name", "=", tag_name)], limit=1)
                if not tag:
                    raise UserError(_("Tag '%s' is not found in the system.") % tag_name)
                tag_ids.append(tag.id)
        new_account = account_obj.create({
            "code": code_no,
            "name": values.get("name"),
            "account_type": account_type,
            "reconcile": is_reconcile,
            "active": is_deprecated,
            "currency_id": currency_get.id if hasattr(currency_get, "id") else currency_get or False,
            "group_id": group_get.id if group_get else False,
            "tax_ids": [(6, 0, tax_ids)] if tax_ids else False,
            "tag_ids": [(6, 0, tag_ids)] if tag_ids else False,
        })
        return new_account

# ---------------------------user-----------------

    
    def find_user_type(self,user):
        user_type=self.env['account.account']
        user_search = user_type.search([('name','=',user)])
        if user_search:
            return user_search
        else:
            raise UserError(_('Field User is not correctly set.'))

# --------------------currency------------------

    
    def find_currency(self, name):
        currency_obj = self.env['res.currency']
        currency_search = currency_obj.search([('name', '=', name)])
        if currency_search:
            return currency_search.id
        else:
            if name == "":
                pass
            else:
                raise UserError(_(' %s currency are not available.') % name)

# -----------------group-------

    
    def find_group(self,group):
        group_type=self.env['account.group']
        group_search = group_type.search([('name','=',group)])

        if group_search:
            return group_search
        else:
            group_id = group_type.create({
                'name' : group
                })
            return group_id
