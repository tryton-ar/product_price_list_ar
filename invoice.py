# This file is part of product_price_list_ar module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields, ModelView
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Equal, Eval, Not, Or
from trytond.transaction import Transaction


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    price_list = fields.Many2One('product.price_list', 'Price List',
        help="Price list to compute the unit price of lines.",
        domain=[('company', '=', Eval('company'))],
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines', [0]))),
            'invisible': Eval('type') == 'in',
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.party.states['readonly'] = (cls.party.states['readonly']
            | Eval('lines', [0]))
        cls.lines.states['readonly'] = (cls.lines.states['readonly']
            | ~Eval('party'))
        cls._buttons.update({
            'update_line_price': {
                'invisible': (
                    (Eval('state') != 'draft') | (Eval('type') == 'in')
                    )
                },
            })

    @fields.depends('currency', 'company')
    def on_change_currency(self):
        if self.currency and self.currency.rate:
            self.currency_rate = (
                self.company.currency.rate / self.currency.rate)
        else:
            self.currency_rate = Decimal('1.0')

    @fields.depends('type', 'price_list', 'party',
        '_parent_party.sale_price_list')
    def on_change_party(self):
        super().on_change_party()
        if self.type == 'in':
            return
        if self.party and self.party.sale_price_list:
            self.price_list = self.party.sale_price_list
        else:
            self.price_list = None

    @classmethod
    @ModelView.button_action(
        'product_price_list_ar.wiz_invoice_update_line_price')
    def update_line_price(cls, invoices):
        pass


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.product.context['currency_rate'] = Eval(
            '_parent_invoice', {}).get('currency_rate')

    def _get_context_invoice_price(self):
        context = {}
        if getattr(self, 'invoice', None):
            if getattr(self, 'currency', None):
                context['currency'] = self.currency.id
            if getattr(self.invoice, 'currency_rate', None):
                context['currency_rate'] = self.invoice.currency_rate
            if getattr(self.invoice, 'party', None):
                context['customer'] = self.invoice.party.id
            if getattr(self.invoice, 'invoice_date', None):
                context['sale_date'] = self.invoice.invoice_date
            if getattr(self.invoice, 'price_list', None):
                context['price_list'] = self.invoice.price_list.id
                context['price_list_currency'] = (
                    self.invoice.price_list.currency.id)
        if self.unit:
            context['uom'] = self.unit.id
        else:
            context['uom'] = self.product.sale_uom.id
        context['taxes'] = [t.id for t in self.taxes]
        return context

    @fields.depends('product', 'unit', 'invoice_type', 'invoice',
        '_parent_invoice.type', 'unit_price', '_parent_invoice.currency',
        '_parent_invoice.currency_rate', '_parent_invoice.party',
        '_parent_invoice.invoice_date', '_parent_invoice.price_list',
        methods=['on_change_with_amount'])
    def on_change_product(self):
        pool = Pool()
        Product = pool.get('product.product')

        super().on_change_product()

        if not self.product:
            return

        if self.invoice and self.invoice.type:
            type_ = self.invoice.type
        else:
            type_ = self.invoice_type
        if type_ == 'out':
            with Transaction().set_context(self._get_context_invoice_price()):
                self.unit_price = Product.get_sale_price([self.product],
                        self.quantity or 0)[self.product.id]
                if self.unit_price is not None:
                    self.unit_price = self.unit_price.quantize(
                        Decimal(1) / 10 ** self.__class__.unit_price.digits[1])

            self.amount = self.on_change_with_amount()


class InvoiceUpdateLinePriceStart(ModelView):
    'Invoice Update Line Price Start'
    __name__ = 'invoice.update_line_price.start'


class InvoiceUpdateLinePrice(Wizard):
    'Invoice Update Line Price'
    __name__ = 'invoice.update_line_price'

    start = StateView('invoice.update_line_price.start',
        'product_price_list_ar.invoice_update_line_price_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Update', 'update', 'tryton-ok', default=True),
            ])
    update = StateTransition()

    def transition_update(self):
        AccountInvoice = Pool().get('account.invoice')

        invoice = AccountInvoice(Transaction().context['active_id'])
        price_list = invoice.price_list
        for line in invoice.lines:
            if (price_list and price_list.product_defined(line.product)
                    is False):
                continue
            line.on_change_product()
            line.save()

        AccountInvoice.update_taxes([invoice])
        return 'end'
