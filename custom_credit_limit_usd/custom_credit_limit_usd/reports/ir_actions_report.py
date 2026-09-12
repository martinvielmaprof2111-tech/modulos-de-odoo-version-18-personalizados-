from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def report_action(self, docids, data=None, **kwargs):
        """Previsualiza informes en pantalla de forma segura, respetando los asistentes/wizards que requieren el parámetro 'data'."""
        res = super().report_action(docids, data=data, **kwargs)

        # Si el reporte fue invocado desde un asistente/wizard que requiere 'data' (ej: aged_receivable),
        # no interceptamos para evitar el error KeyError: 'data'.
        if data:
            return res

        if isinstance(res, dict) and res.get('report_type') == 'qweb-pdf':
            # 1. Normalizar los IDs del documento
            if isinstance(docids, int):
                docids_list = [docids]
            elif isinstance(docids, (list, tuple)):
                docids_list = list(docids)
            else:
                docids_list = [docids]

            # 2. Si el documento tiene vista previa nativa en el portal (Facturas / Ventas), la invocamos
            if self.model and len(docids_list) == 1:
                record = self.env[self.model].browse(docids_list[0])

                if hasattr(record, 'preview_invoice'):
                    return record.preview_invoice()

                if hasattr(record, 'preview_sale_order'):
                    return record.preview_sale_order()

            # 3. Para REPORTES ESTÁNDAR / STUDIO (stock.picking, compras, etc.):
            # Se abre la vista previa HTML limpia con contexto de compañías
            if docids_list:
                docids_str = ",".join(map(str, docids_list))
                company_ids = self.env.context.get('allowed_company_ids') or [self.env.company.id]
                company_param = ",".join(map(str, company_ids))

                return {
                    'type': 'ir.actions.act_url',
                    'url': f'/report/html/{self.report_name}/{docids_str}?cids={company_param}',
                    'target': 'new',
                }

        return res