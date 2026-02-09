# 💡 Sistema de LEDs - Manual de Funcionamiento

## Descripción General

El sistema de UI mejorado incluye **2 LEDs visuales** en la esquina superior derecha que muestran el estado del sistema en tiempo real.

---

## LED 1: HTTP Status 🌐

**Ubicación**: Arriba a la derecha, etiqueta "HTTP"

### Comportamiento:

```
┌─────────────────────────────────────────────────────┐
│  ACCIONES                      | RESPUESTA DEL LED   │
├─────────────────────────────────────────────────────┤
│ Petición HTTP exitosa (200 OK) │ 🟢 Titila VERDE    │
│ Error servidor (500+)          │ 🔴 Titila ROJO     │
│ Forbidden (403)                │ 🔴 Titila ROJO ALARM│
│ Too Many Requests (429)        │ 🔴 Titila ROJO ALARM│
│ Otros 4xx                      │ 🔴 Titila ROJO     │
│ Sin peticiones                 │ ⚫ APAGADO         │
└─────────────────────────────────────────────────────┘
```

### Duración del Parpadeo:
- **Prendido**: 200ms
- **Apagado**: 200ms
- **Total**: ~400ms por parpadeo completo

### Causas de Activación:
- SNAPSHOT event (lectura del portal)
- UPDATE event (actualización de datos)
- HTTP_ERROR event (error en la petición)

---

## LED 2: Ofertas Real 📊

**Ubicación**: Arriba a la derecha, etiqueta "Ofertas"

### Comportamiento:

```
┌─────────────────────────────────────────────────────┐
│  EVENTO                        | RESPUESTA DEL LED   │
├─────────────────────────────────────────────────────┤
│ Cambio de mejor oferta         │ 🟢 SE ENCIENDE     │
│   • Mantiene verde por 3 seg   │                    │
│   • Si NO hay más cambios      │ ⚫ SE APAGA         │
│                                │                    │
│ Cambio DURANTE esos 3 seg      │ 🟢 PARPADEA VERDE  │
│   • Se reinician los 3 seg     │                    │
│   • Cada cambio suma parpadeo  │                    │
│                                │                    │
│ Sin cambios de oferta          │ ⚫ TOTALMENTE APAGADO
└─────────────────────────────────────────────────────┘
```

### Timeline de Ejemplo:

```
TIEMPO  | EVENTO                    | ESTADO DEL LED
────────┼───────────────────────────┼─────────────────────
0 seg   | Cambio oferta 1           | 🟢 SE ENCIENDE
        | (inicia timer de 3 seg)   |
────────┼───────────────────────────┼─────────────────────
1.5 seg | Cambio oferta 2           | 🟢 PARPADEA
        | (reinicia timer a 0)      |
────────┼───────────────────────────┼─────────────────────
2.8 seg | Cambio oferta 3           | 🟢 PARPADEA
        | (reinicia timer a 0)      |
────────┼───────────────────────────┼─────────────────────
5.8 seg | (3 seg sin cambios)       | ⚫ SE APAGA
────────┼───────────────────────────┼─────────────────────
6 seg   | Sin eventos               | ⚫ MANTIENE APAGADO
```

### Duración del Parpadeo:
- **Prendido**: 200ms
- **Apagado**: 200ms
- **Total de vida**: 3 segundos (o más si hay eventos)

### Causas de Activación:
- Cambio en `mejor_txt` (mejor oferta del sistema)
- SOLO si el cambio es REAL del portal (no cambios del usuario)

---

## Interpretación del Usuario Final

### ✅ Verde titilante (HTTP)
> El sistema está comunicándose exitosamente con el portal cada segundo.

### 🔴 Rojo titilante (HTTP)
> Hubo problemas en la comunicación con el portal. Revisar conexión.

### 🟢 Verde permanente (Ofertas)
> Hay cambios de ofertas en tiempo real. El sistema está sincronizado.

### 🟢 Verde con parpadeos frecuentes (Ofertas)
> Múltiples cambios de ofertas ocurriendo en corto tiempo. ¡Subasta muy activa!

### ⚫ Ambos apagados
> Sistema en espera o sin actividad de peticiones/cambios.

---

## Indicadores Combinados

| HTTP LED | Ofertas LED | Significado |
|----------|-------------|-------------|
| 🟢 Titila | ⚫ Apagado | Peticiones normales, sin cambios de oferta |
| 🟢 Titila | 🟢 Encendido | Peticiones OK + cambios de ofertas detectados |
| 🔴 Titila | 🟢 Encendido | Error HTTP pero hay cambios de oferta (datos en caché) |
| 🔴 Titila | ⚫ Apagado | Error persistente en comunicación |
| ⚫ Apagado | ⚫ Apagado | Sistema pausado o inactivo |

---

## Detalles Técnicos

### Archivos Involucrados:
- `app/ui/led_indicator.py` - Clases de LEDs
- `app/ui/event_handler.py` - Disparo de eventos a LEDs
- `app/ui/app.py` - Integración con UI

### Callbacks Registrados:
```python
self.event_processor.on_http_event = self.http_led.on_http_status
self.event_processor.on_offer_changed = self.offer_led.on_offer_changed
```

### Métodos de LEDs:

**HTTPStatusLED:**
- `on_http_status(status_code: int)` - Parpadea según código HTTP

**OfferChangeLED:**
- `on_offer_changed()` - Enciende por 3 seg, parpadea si hay múltiples

---

## Solución de Problemas

### Los LEDs no parpadean
- ✅ Verificar que hay eventos siendo generados
- ✅ Revisar logs en la ventana principal
- ✅ Comprobar que modo MOCK o PLAYWRIGHT está activo

### LED HTTP no se ve
- El LED HTTP solo titila cuando hay peticiones HTTP
- En modo sin collector, no habrá peticiones
- Iniciar el collector con "▶️ Abrir navegador"

### LED Ofertas no se prende
- Solo se enciende si la mejor oferta CAMBIA
- En modo de prueba (MOCK), esperar a que el scenario genere cambios
- El LED se apaga si pasan 3 segundos sin cambios

### Parpadeos muy rápidos
- Indica múltiples cambios de ofertas en poco tiempo
- Comportamiento normal en subastas muy activas
- No es un error

