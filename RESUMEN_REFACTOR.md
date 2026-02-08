# 🎯 Resumen Ejecutivo: Refactorización del Simulador

## El Problema

Actualmente el simulador (`app/core/simulator.py`) tiene **datos hardcodeados** dispersos por todo el código:
- Valores inventados: `base_best = 18_000_000.0 + (int(rid) % 7) * 1_250_000.0`
- Lógica de cambios hardcodeada: 1% cada 60 segundos
- RNG con semilla fija
- Imposible predecir logs para debugging

**Resultado**: Escenarios de prueba no reproducibles, debugging difícil, tests no determinísticos.

---

## La Solución

### Sistema Basado en JSON con Datos Reales

Migrar de código hardcodeado a archivos JSON que contengan **responses reales del portal**.

**Formato**:
```json
{
  "scenario_name": "controlled_real_scenario",
  "timeline": [
    {
      "tick": 0,
      "hora": "10:00:00",
      "status": 200,
      "renglones": [
        {
          "id_renglon": "836160",
          "response_json": {
            "d": "<DATOS_REALES_DEL_PORTAL>"
          }
        }
      ]
    },
    {
      "tick": 3,
      "hora": "10:03:00",
      "status": 200,
      "renglones": [...]
    },
    {
      "tick": 5,
      "hora": "10:05:00",
      "status": 500,
      "error_message": "Internal Server Error"
    }
  ]
}
```

**Ventajas**:
- ✅ **Previsibilidad total**: Logs 100% predecibles
- ✅ **Datos reales**: Copy/paste desde DevTools
- ✅ **Control fino**: Hora + status HTTP + cambios exactos
- ✅ **Sin código**: Nuevos escenarios sin tocar el código
- ✅ **Reproducibilidad**: Compartir escenarios en JSON

---

## Implementación

### Fase 1: ScenarioLoader (2-3 horas)
- Crear `app/core/scenario_loader.py`
- Parser del formato real: `"d": "[...]@@presupuesto@@oferta_min@@"`
- Validación de schema JSON

### Fase 2: SimulatorV2 (3-4 horas)
- Crear `app/core/simulator_v2.py`
- Lógica basada en timeline
- Manejo de status HTTP (200, 500, 502, 503)
- Compatible con API actual

### Fase 3: Integración (2 horas)
- Adaptar `MockCollector` para usar v2
- Parámetro `--scenario` en `main.py`
- 5 escenarios de prueba completos
- Tests end-to-end

### Fase 4: Deprecación (1 hora)
- Renombrar `simulator.py` → `simulator_legacy.py`
- Actualizar documentación
- Commit final

**Total estimado**: 8-10 horas

---

## Escenarios Creados

Ya están disponibles:

1. **scenario_controlled_real.json** ✅
   - 4 cambios de precio reales
   - 2 errores HTTP 500
   - Datos capturados del portal real

2. **scenario_basic.json** ✅
   - 3 renglones estables
   - Sin cambios (baseline)

3. **scenario_price_war.json** ✅
   - Precios caen 1% por minuto
   - 2 renglones con cambios independientes

4. **scenario_http_errors.json** ✅
   - Errores HTTP frecuentes
   - Prueba políticas de seguridad

5. **scenario_specific_timeline.json** ✅
   - Timeline exacto con eventos predefinidos
   - Validación de logs esperados

---

## Cómo Capturar Datos Reales

**Ver**: [GUIA_CAPTURA_DATOS.md](GUIA_CAPTURA_DATOS.md)

**Resumen rápido**:
1. Abre DevTools (F12) en el portal
2. Network → XHR → Busca `BuscarOfertas`
3. Copy Response
4. Pega en el JSON del escenario
5. ¡Listo! Escenario 100% realista

---

## Criterios de Éxito

- [x] Plan documentado
- [x] Escenarios JSON creados
- [x] Formato con datos reales definido
- [ ] ScenarioLoader implementado
- [ ] SimulatorV2 implementado
- [ ] Tests pasando
- [ ] Logs 100% predecibles
- [ ] 0% código hardcodeado

---

## Próximos Pasos

1. ✅ **Aprobación**: Revisar y aprobar este plan
2. 🚧 **Fase 1**: Implementar ScenarioLoader
3. 🚧 **Fase 2**: Implementar SimulatorV2
4. 🚧 **Fase 3**: Integración completa
5. 🚧 **Fase 4**: Deprecar simulator legacy

---

## Documentación Completa

- 📋 [PLAN_REFACTOR_SIMULATOR.md](PLAN_REFACTOR_SIMULATOR.md) - Plan detallado con código
- 📖 [GUIA_CAPTURA_DATOS.md](GUIA_CAPTURA_DATOS.md) - Cómo capturar del portal
- 📝 [README.md](README.md) - Documentación general del proyecto

---

**Estado actual**: Plan aprobado, listo para iniciar implementación 🚀
