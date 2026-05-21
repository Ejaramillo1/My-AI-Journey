---
title: "La Guía del No-Ingeniero para Correr un Agente de IA"
date: 2026-05-21
draft: false
tags: ["AI Agents", "Principiantes", "Self-Hosting", "No-Code", "Productividad"]
categories: ["AI & Automation"]
author: "Ed Jaramillo"
description: "No soy ingeniero de software. Soy analista de precios. Y corro mi propio agente de IA 24/7. Esto es lo que nadie me dijo sobre cómo empezar."
ShowToc: true
ShowBreadCrumbs: true
---

No soy ingeniero de software. Soy analista de precios competitivos.

Escribo SQL y DAX, no microservicios en Python. Cuando decidí montar mi propio agente de IA, estaba completamente fuera de mi profundidad desde el día uno.

La buena noticia: tú también puedes hacerlo. La noticia honesta: tomará más tiempo del que crees, y la documentación asume que sabes cosas que quizás no sepas.

## Los Puntos de Confusión

### ¿Cuál Terminal Es Cuál?

Tienes tu terminal de Windows, tu terminal de WSL, tu terminal de Docker, y la terminal del sandbox dentro de todo eso. Pasé horas ejecutando comandos en el lugar equivocado.

### ¿Qué Código Corre Dónde?

Las políticas de OpenShell corren en el host. La lógica del agente corre en el sandbox. La configuración del gateway corre en el gateway. Mézclalos y nada funciona.

### La Indentación en YAML Te Va a Romper

Dos espacios vs cuatro espacios. Tabs vs espacios. Una sola línea desalineada y tu configuración es invisible para el sistema. Sin mensaje de error. Solo silencio.

## Lo Que Sí Me Ayudó

1. **Dibuja las capas.** Host → WSL → Docker → Sandbox → Gateway. Etiqueta qué corre dónde.
2. **Guarda tus API keys en un gestor de contraseñas.** Solía generar keys y perderlas en una semana. Ahora tengo un sistema.
3. **Los rebuilds pasan.** No guardes nada valioso dentro del sandbox. Es desechable por diseño.
4. **Empieza con una sola tarea.** Intenté automatizar todo de golpe. Elige un flujo de trabajo. Hazlo funcionar. Luego expande.
5. **Prueba las políticas de red un endpoint a la vez.** El sandbox bloquea todo por defecto. Agrega cosas lentamente.

## Por Qué Vale la Pena

Después de toda la frustración, tengo un agente de IA que corre mis briefings diarios, rastrea mis finanzas, investiga competidores y redacta mis correos. Trabaja mientras duermo. Cuesta casi nada operarlo. Y lo construí yo — no un equipo de devs, no un vendor. Yo.

Si un analista de precios en Tijuana puede hacer esto, tú probablemente también.
