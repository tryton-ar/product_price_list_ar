# This file is part of product_price_list_ar module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal, ROUND_HALF_UP
from sql import Table

from trytond.model import fields, ModelView
from trytond.modules.product import price_digits
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button


class PriceList(metaclass=PoolMeta):
    'Price List'
    __name__ = 'product.price_list'

    currency = fields.Many2One('currency.currency', 'Currency',
        required=True)

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.id

    def product_defined(self, product):
        '''
        If the product is defined in the list
        or in the parent list, then return True
        '''
        cursor = Transaction().connection.cursor()
        lines = Table('product_price_list_line')

        cursor.execute(*lines.select(lines.id,
            where=(lines.product == product.id) &
                (lines.price_list == self.id)))
        if cursor.fetchall():
            return True
        return False

    def get_context_formula(self, party, product, unit_price, quantity, uom,
            pattern=None):
        pool = Pool()
        PriceList = pool.get('product.price_list')
        Currency = pool.get('currency.currency')

        res = super().get_context_formula(party, product, unit_price,
                quantity, uom, pattern=None)
        context = Transaction().context
        if context.get('price_list') and context.get('currency'):
            price_list = PriceList(context.get('price_list'))
            currency = Currency(context.get('currency'))
            if price_list.currency != currency:
                if price_list.currency.rate != 0:
                    rate = Decimal(str(
                        currency.rate / price_list.currency.rate))
                    if isinstance(res['names']['unit_price'], Decimal):
                        res['names']['unit_price'] /= rate
                    if isinstance(res['names']['cost_price'], Decimal):
                        res['names']['cost_price'] /= rate
                    if isinstance(res['names']['list_price'], Decimal):
                        res['names']['list_price'] /= rate
        return res

    def compute(self, party, product, unit_price, quantity, uom,
            pattern=None):
        'Compute price based price list currency'
        pool = Pool()
        PriceList = pool.get('product.price_list')
        Currency = pool.get('currency.currency')

        context = Transaction().context
        unit_price = super().compute(party, product, unit_price, quantity,
            uom, pattern=None)
        if context.get('price_list') and context.get('currency'):
            price_list = PriceList(context.get('price_list'))
            if price_list.product_defined(product) is False:
                return unit_price
            currency = Currency(context.get('currency'))
            if price_list.currency != currency:
                rate = None
                if context.get('currency_rate'):
                    if int(context.get('currency_rate')) == 1:
                        # currency_rate = 1 can not be used
                        if price_list.currency.rate == 0:
                            rate = Decimal('1.0')
                        else:
                            rate = Decimal(str(
                                currency.rate / price_list.currency.rate))
                    else:
                        rate = Decimal(context.get('currency_rate'))
                else:
                    # Calculate rate from currencies
                    if price_list.currency.rate == 0:
                        rate = Decimal('1.0')
                    else:
                        rate = Decimal(str(
                            currency.rate / price_list.currency.rate))
                unit_price *= rate

        return unit_price


class PriceListLine(metaclass=PoolMeta):
    'Price List Line'
    __name__ = 'product.price_list.line'

    @classmethod
    def compute_currency(cls, from_currency, amount, to_currency,
            currency_rate, round=True):
        pool = Pool()
        Company = pool.get('company.company')

        if to_currency == from_currency:
            if round:
                return to_currency.round(amount)
            else:
                return amount

        company = Company(Transaction().context['company'])
        if from_currency == company.currency:
            from_currency_rate = currency_rate
            currency_rate = Decimal('1.0')
        else:
            from_currency_rate = Decimal('1.0')

        if round:
            return to_currency.round(
                amount * currency_rate / from_currency_rate)
        else:
            return amount * currency_rate / from_currency_rate

    @classmethod
    def _recompute_price_by_fixed_amount(cls, line, new_unit_price):
        values = {
            'formula': new_unit_price,
            }
        return values

    @classmethod
    def recompute_price_by_fixed_amount(cls, lines, unit_price):
        to_write = []
        for line in lines:
            new_values = line._recompute_price_by_fixed_amount(line,
                unit_price)
            if new_values:
                to_write.extend(([line], new_values))
        if to_write:
            cls.write(*to_write)

    @classmethod
    def _recompute_price_by_percentage(cls, line, factor):
        new_list_price = (line.formula * factor).quantize(
            Decimal('1.'), rounding=ROUND_HALF_UP)
        values = {
            'formula': new_list_price,
            }
        return values

    @classmethod
    def recompute_price_by_percentage(cls, lines, percentage):
        to_write = []
        factor = Decimal(1) + Decimal(percentage)
        for line in lines:
            new_values = cls._recompute_price_by_percentage(line, factor)
            if new_values:
                to_write.extend(([line], new_values))
        if to_write:
            cls.write(*to_write)


class Currency(metaclass=PoolMeta):
    __name__ = 'currency.currency'

    @classmethod
    def compute(cls, from_currency, amount, to_currency, round=True):
        pool = Pool()
        PriceListLine = pool.get('product.price_list.line')

        currency_rate = Transaction().context.get('currency_rate')
        if currency_rate:
            return PriceListLine.compute_currency(from_currency, amount,
                to_currency, currency_rate, round)
        return super().compute(from_currency, amount, to_currency, round)


class ProductPriceRecomputeStart(ModelView):
    'Recompute Price List - Start'
    __name__ = 'product.price_list.recompute_price.start'

    method = fields.Selection([
            ('fixed_amount', 'Fixed Amount'),
            ('percentage', 'Percentage'),
            ], 'Recompute Method', required=True)
    percentage = fields.Float('Percentage', digits=(16, 4),
        states={
            'invisible': Eval('method') != 'percentage',
            'required': Eval('method') == 'percentage',
            },
        depends=['method'])
    unit_price = fields.Numeric('Unit Price', digits=price_digits,
        states={
            'invisible': Eval('method') != 'fixed_amount',
            'required': Eval('method') == 'fixed_amount',
            }, depends=['method'])
    products = fields.Many2Many('product.product', None, None, 'Products')

    @staticmethod
    def default_unit_price():
        return Decimal('0')

    @staticmethod
    def default_percentage():
        return float(0)

    @staticmethod
    def default_method():
        return 'percentage'

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/form//label[@id="percentage_"]', 'states', {
                    'invisible': Eval('method') != 'percentage',
                    }),
            ]


class ProductPriceRecompute(Wizard):
    'Recompute Product Price'
    __name__ = 'product.price_list.recompute_price'

    start = StateView('product.price_list.recompute_price.start',
        'product_price_list_ar.price_list_recompute_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Recompute', 'recompute_', 'tryton-ok', default=True),
            ])
    recompute_ = StateTransition()

    def get_additional_args(self):
        method_name = 'get_additional_args_%s' % self.start.method
        if not hasattr(self, method_name):
            return {}
        return getattr(self, method_name)()

    def get_additional_args_percentage(self):
        return {
            'percentage': self.start.percentage,
            }

    def transition_recompute_(self):
        pool = Pool()
        Line = pool.get('product.price_list.line')

        method_name = 'recompute_price_by_%s' % self.start.method
        method = getattr(Line, method_name)
        if method:
            domain = []
            if self.start.products:
                products = [s.id for s in list(self.start.products)]
                domain.append(('product', 'in', products))
            method(Line.search(domain), **self.get_additional_args())
        return 'end'
