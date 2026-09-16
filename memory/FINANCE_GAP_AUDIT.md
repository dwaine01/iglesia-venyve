# Auditoría de brechas — Mega‑Bloque G Finanzas

Fecha de auditoría inicial: 2026-09-16  
Alcance: operación diaria de iglesia sobre el núcleo existente `finance_*`, Persona 360 y RBAC jerárquico.  
Regla: **PASS** exige flujo funcional probado; la mera presencia de código no basta.

## Matriz inicial antes de completar brechas

| # | Estado inicial | Pantalla existente | API / modelo / colección | Efecto contable y RBAC | Evidencia y brecha exacta |
|---|---|---|---|---|---|
| 1 | PARTIAL | `/finanzas/contribuciones` | `POST /api/finance/contributions` → `finance_contributions` | Crea asiento balanceado enviado; requiere `finance.manage` | Busca Persona canónica y admite splits por fondo, pero solo un concepto por transacción y no existe flujo rápido por sobre. |
| 2 | PARTIAL | Contribuciones + Configuración + Campañas | `finance_funds`, `finance_campaigns`, `finance_contribution_types` | Fondo y campaña llegan al asiento | Fondos/campañas son configurables; tipos están limitados y faltan descripción/notas/destino especial flexible. |
| 3 | PARTIAL | Formulario de contribución | `ContributionCreate.payment_method` | Método se persiste | Existen efectivo, cheque, tarjeta, ACH, Pushpay y otro; falta Zelle y transferencia explícita en UI/contrato. |
| 4 | PARTIAL | Formulario de contribución | Contribución manual + histórico por `person_id` | Produce asiento y auditoría | El flujo manual funciona, pero Zelle no existe como método seleccionable. |
| 5 | PARTIAL | Sin vista de historial de cambios | `created_at`, `created_by_user_id`, `finance_audit_events` | Auditoría de creación | Falta `updated_at`, modificador, corrección versionada y comparación antes/después. |
| 6 | PARTIAL | `PersonFinanceSection` dentro de Perfil 360 | `GET /api/finance/persons/{person_id}/contributions` | Solo `finance.read`; datos ligados a Persona | Devuelve total/lista, pero faltan resumen anual por concepto/fondo, filtros, método, referencia y ficha financiera rápida. La pestaña puede quedar deshabilitada por `sections_available`. |
| 7 | PASS | Pestaña Finanzas solo para autorizados | Todas las rutas usan `reader/manager` | Backend exige `finance.read/manage`; pastor conserva acceso maestro | Iteration 15 verificó 401 sin JWT, 403 sin permiso y que líderes/personas no heredan Finanzas. Conservar. |
| 8 | MISSING | No existe | No existe endpoint/carta | Sin efecto contable; debe requerir `finance.read` | Falta configuración institucional/legal, elegibilidad por tipo, borrador anual, impresión/PDF y trazabilidad de emisión. |
| 9 | MISSING | No existe | No existe endpoint de corrección | No hay reversión/ajuste | Falta conservar original, motivo, actor, antes/después y tratamiento especial de asientos contabilizados/períodos cerrados. |
| 10 | PARTIAL | `FinanceBatchesPanel` | `finance_batches`, `/batches`, `/counts` | Doble conteo y bloqueo por diferencia | Existe agrupación y dos conteos independientes; faltan servicio/nombre, sobres, desglose esperado/contado por concepto y justificación autorizada de diferencias. |
| 11 | PARTIAL | Operación → Depósitos | `finance_deposits`, `DepositCreate` | Reclasifica fondos no depositados hacia banco sin duplicar ingreso | Existe traza contribución→batch→depósito→asiento; faltan comprobante completo en flujo batch y actualización real al conciliar. |
| 12 | PARTIAL | Contribuciones / Configuración | Tipos seed: tithe/offering/donation; fondos separados | Tipo define ingreso; fondo define restricción/destino | La separación conceptual es correcta, pero faltan Misiones, Pro‑Templo, proyectos y otros tipos configurables. |
| 13 | PARTIAL | Operación → Gastos/Proveedores | `finance_vendors`, `finance_expenses`, `finance_payments` | Flujo enviado→revisado→aprobado→pago con asiento | Backend tiene varios campos útiles, pero UI omite proveedor, factura, vencimiento, categoría, ministerio, documentos, método/referencia y estado programado/pagado. |
| 14 | PARTIAL | Operación → Gastos | Cuentas de gasto configurables | Cuenta/fondo llegan al asiento de pago | Admite gastos por cuenta, pero faltan catálogo operativo amigable y clasificación fija/recurrente vs. variable. |
| 15 | MISSING | No existe | No existe obligación recurrente | No hay generación idempotente de cuentas por pagar | Falta calendario, próxima fecha, frecuencia y creación controlada sin duplicados. |
| 16 | PARTIAL | Gastos genéricos | Proveedor/beneficiario y cuentas configurables | Puede contabilizarse como gasto | No existe clasificación explícita empleado/compensación ni preparación para futura integración payroll. No se construirá payroll. |
| 17 | PARTIAL | Gastos genéricos | Campos de gasto y pago | Aprobación y asiento existentes | Puede modelarse parcialmente, pero faltan beneficiario/tipo y clasificación contable/fiscal libre y revisable sin asumir salario/ofrenda. |
| 18 | PARTIAL | Reportes por fondo y campañas | `fund-balances`, `budget-vs-actual`, contribuciones/gastos | Agrega asientos contabilizados | Falta una vista por fondo/proyecto con entradas, gastos, presupuesto, disponible y drill-down real. |
| 19 | PARTIAL | Operación → Presupuestos | `finance_budgets` | Reporte presupuesto vs. real | Existe año/fondo/cuenta y `ministry_id` en backend; faltan proyecto/categoría, UI completa, filtros y drill-down. |
| 20 | PARTIAL | `/finanzas` | `/dashboard` | Usa transacciones reales | Muestra fondos, pendientes, depósitos y gastos abiertos; faltan entró/salió/efectivo/deuda/próximos pagos/presupuesto. |
| 21 | PARTIAL | Configuración → Períodos | `finance_periods`, `/periods/{id}/close` | Impide aprobar asiento en período cerrado | Solo comprueba asientos no contabilizados; faltan checklist de conteos, depósitos, AP, conciliación, bloqueo integral, reapertura y ajuste trazable. |
| 22 | PARTIAL | `/finanzas/conciliacion` | `finance_reconciliations` | Calcula diferencia contra asientos contabilizados | No marca movimientos/depósitos/pagos como conciliados, no excluye reutilizados y el cálculo carece de saldo inicial/movimientos pendientes. |
| 23 | BLOCKED | Integraciones muestra bloqueo real | `/integrations/pushpay`, adapter placeholder | Sin importación real ni asientos simulados | Correctamente **BLOCKED/MOCKED** por ausencia de credenciales sandbox. |
| 24 | PARTIAL | `/finanzas/reportes` | `/reports/{report_key}` | Solo `finance.read` | Hay reportes base; faltan filtros ricos, contribuyentes/familias/métodos, AP, depósitos, conciliación y reportes ejecutivos sin detalle innecesario. |
| 25 | PARTIAL | Búsqueda durante alta | Directorio canónico + endpoint por persona | Usa `person_id` | Busca Persona para registrar, pero no ofrece buscar→histórico→nueva contribución→carta→transacciones en un flujo corto. |
| 26 | PARTIAL | Todas las rutas financieras | N/A | RBAC conservado | Navegación responsive general PASS; falta certificar y optimizar nuevos flujos de conteo/ficha/carta en desktop, tablet y móvil. |
| 27 | PASS | Este documento | Trazabilidad a APIs/colecciones | Incluye asiento y RBAC por requisito | Matriz inicial completada antes de implementación. Debe actualizarse con verificación final. |
| 28 | MISSING | No existe prueba completa | Pruebas actuales cubren piezas | No existe secuencia total solicitada | Iteration 15 cubre idempotencia/RBAC/asientos, pero no el ciclo real completo con carta, corrección, AP, depósito y conciliación. |

## Decisión de implementación

- Conservar sin rehacer: Persona 360, `person_id`, fondos, cuentas, motor de asientos, triple aprobación, RBAC financiero, auditoría base, campañas, presupuestos, batches, depósitos, reportes y adapter Pushpay bloqueado.
- Extender las colecciones existentes y añadir, cuando el dominio lo exige, añadir únicamente entidades subordinadas del mismo núcleo: obligaciones recurrentes, correcciones e historial de cartas.
- No crear perfiles financieros alternos ni duplicar fondos, cuentas, Personas o libros contables.
- Todas las nuevas lecturas y mutaciones financieras continuarán protegidas en backend por `finance.read` o `finance.manage`; aprobaciones/reaperturas/configuración legal quedan reservadas al pastor.

## Matriz final después de implementación y certificación

Fecha de certificación: 2026-09-16  
Resultado: **27 PASS · 0 PARTIAL · 0 MISSING · 1 BLOCKED (Pushpay)**.  
Evidencia independiente: `/app/test_reports/iteration_16.json` — backend 100%, frontend 100%, E2E real PASS, responsive PASS, build PASS y cleanup PASS.

| # | Estado final | Pantalla → API → colección/modelo | Asiento / RBAC | Prueba ejecutada |
|---|---|---|---|---|
| 1 | PASS | Contribuciones rápidas → `POST /contributions` → `finance_contributions` ligado a Persona 360 | Un asiento balanceado admite múltiples conceptos; `finance.manage` | E2E: mismo sobre $200 diezmo + $20 ofrenda por `person_id`. |
| 2 | PASS | Configuración/Contribuciones → tipos, fondos y campañas → `finance_contribution_types`, `finance_funds`, `finance_campaigns` | Cada línea conserva tipo, fondo, proyecto, descripción y elegibilidad | E2E: donación designada Pro‑Templo con campaña; configuración extensible sin código. |
| 3 | PASS | Selector Método → `ContributionCreate.payment_method` | Método persiste en contribución y auditoría | Contrato y UI verifican cash, check, Zelle, ACH, transfer, Pushpay y other. |
| 4 | PASS | Nueva contribución → Persona + Zelle + referencia | Asiento a fondos no depositados e histórico de Persona | E2E: Zelle $300, fecha y referencia bancaria, luego depósito/conciliación. |
| 5 | PASS | Registro/corrección → contribuciones, correcciones y auditoría | `created/updated_by`, timestamps, before/after, motivo y actor | E2E valida creación, modificación trazable y eventos de auditoría. |
| 6 | PASS | Finanzas → Contribuyentes → `/contributors/{person_id}` | Solo `finance.read`; no crea perfil paralelo | Filtros año/fechas/tipo/fondo/método, totales y tabla probados. |
| 7 | PASS | Todas las vistas financieras → dependencies `reader/manager` | Backend devuelve 401/403; Finanzas no se hereda por liderazgo | E2E revoca Finanzas y confirma 403 desde token de la Persona. |
| 8 | PASS | Contribuyente → Generar carta → `finance_annual_statements` | Solo transacciones elegibles; emisión auditada | E2E genera snapshot anual; UI produce PDF. Sin texto aprobado, marca borrador pendiente legal. |
| 9 | PASS | Corregir → `/contributions/{id}/correct` → `finance_contribution_corrections` | Conserva original; void si no posteado, reversión si posteado; fecha contable abierta | E2E valida ambos caminos y depósito `adjustment_required`. |
| 10 | PASS | Operación → Conteos → `finance_batches` | Sesión `collecting`, captura por `batch_id`, doble conteo, desglose y diferencia autorizada | E2E abre sesión antes de sobres, captura 3 transacciones y reconcilia $620. |
| 11 | PASS | Conteo → Depósito → `finance_deposits` | Reclasifica fondos no depositados a banco sin volver a reconocer ingreso | E2E conserva contribución→batch→depósito→journal→reconciliation. |
| 12 | PASS | Configuración/Contribuciones | Tipo y fondo son campos distintos en cada asignación | Seed/configuración incluye diezmo, ofrenda, donación, misiones, Pro‑Templo, proyecto y otro. |
| 13 | PASS | Operación → Cuentas por pagar → vendors/expenses/payments/docs | Flujo submitted→reviewed→approved→scheduled→paid y asiento de pago | E2E valida factura, beneficiario, fondo, aprobación triple, pago y comprobante GridFS. |
| 14 | PASS | Cuentas por pagar → categorías/cuentas | Cuenta de gasto y fondo llegan al asiento; naturaleza fixed/variable | UI y E2E registran Internet como gasto fijo con cuenta operacional. |
| 15 | PASS | Operación → Recurrentes → `finance_recurring_obligations/runs` | Genera AP, no pago ni asiento duplicado | E2E ejecuta dos veces la misma fecha: 1 generación y luego 0. |
| 16 | PASS | AP → beneficiary type employee + clasificación libre | Se contabiliza como gasto; no existe payroll ficticio | Contrato/UI preparados para futura integración payroll sin clasificación fiscal automática. |
| 17 | PASS | AP → beneficiary type pastor + clasificación revisable | Fondo, aprobación, método, comprobante, asiento y conciliación comunes | No hay supuesto hardcoded de salario/ofrenda; la clasificación es texto administrable. |
| 18 | PASS | Presupuesto y fondos / Campañas → activity endpoints | Entradas y gastos provienen de contribuciones/asientos; disponible calculado | E2E verifica General y Pro‑Templo, campaña, presupuesto y drill‑down. |
| 19 | PASS | Operación → Presupuesto → `finance_budgets` | Año + cuenta + fondo + ministerio + proyecto + categoría | E2E crea presupuesto y valida actividad real; UI ofrece drill‑down. |
| 20 | PASS | Resumen → `/dashboard` | Solo asientos/transacciones reales, sin demos | Muestra ingresó, salió, tenemos, debemos, próximos, fondos y presupuesto. |
| 21 | PASS | Configuración → Períodos → checklist/close/reopen | Cierre bloquea nuevas contabilizaciones; reapertura solo pastor con motivo | E2E checklist limpio, cierre, 409 en período cerrado y reapertura auditada. |
| 22 | PASS | Conciliación → `finance_reconciliations` | Saldo inicial + movimientos = final; marca journals/deposits/payments solo si balancea | E2E concilia depósito $620 menos pago $120 contra saldo $500. |
| 23 | BLOCKED | Integraciones → adapter Pushpay | No realiza llamadas ni simula importación | Validado status `blocked_credentials_required`; requiere credenciales sandbox reales. |
| 24 | PASS | Reportes → `/reports/*` + ficha de contribuyente | `finance.read`; dashboard general no revela individuos | Reportes de ingresos, gastos, fondos, persona/familia, método, AP, depósitos, conciliación, recurrentes y auditoría. |
| 25 | PASS | Contribuyentes → búsqueda rápida → ficha/nueva/carta/corrección | Consulta canónica por `person_id`, siempre dentro de Finanzas | UI real desktop/móvil verificada; búsqueda E2E devuelve la Persona usada. |
| 26 | PASS | Todas las rutas financieras | Mismos endpoints RBAC en cualquier viewport | Desktop 1920×800 y móvil 390×844 verificados con overflow `[]`; build PASS. |
| 27 | PASS | Esta matriz inicial + final | Trazabilidad completa a API, colección, asiento, RBAC y prueba | Revisión inicial preservada; cierre actualizado después de implementación. |
| 28 | PASS | `test_finance_daily_operation_e2e.py` | Ciclo contable completo con triple aprobación y auditoría | RECIBIR→IDENTIFICAR→CLASIFICAR→CONTAR→DEPOSITAR→CONTABILIZAR→PAGAR→CONCILIAR→REPORTAR→AUDITAR; cleanup cero QA. |

## Estado de cierre

- No quedan requisitos internos `PARTIAL` o `MISSING` dentro del alcance autorizado de Mega‑Bloque G.
- Pushpay es la única dependencia `BLOCKED/MOCKED` y no se declarará integrada sin sandbox real.
- La plantilla anual puede producir borrador; su texto legal/fiscal solo pasa a aprobado mediante acción pastoral explícita.
- Las pruebas eliminan contribuciones, asientos, batches, depósitos, AP, pagos, documentos GridFS, campañas, presupuestos, períodos, conciliaciones, cartas y auditorías QA; también restauran permisos.