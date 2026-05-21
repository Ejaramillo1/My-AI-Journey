---
title: "Instalé NemoClaw 20 Veces y Esto Es Lo Que Aprendí"
date: 2026-05-21
draft: false
tags: ["Agentes IA", "NemoClaw", "Self-Hosting", "Open Source", "Linux"]
categories: ["IA y Automatización"]
author: "Ed Jaramillo"
description: "La mayoría de los tutoriales te dicen que son tres comandos. Lo reinstalé 20 veces. Esto es lo que los tutoriales no te cuentan sobre hospedar tu propio agente de IA."
ShowToc: true
ShowBreadCrumbs: true
---

La mayoría de los tutoriales te dicen que son tres comandos y ya está. Lo reinstalé 20 veces. Esto es lo que los tutoriales no te cuentan.

## La Arquitectura Que Necesitas Entender Antes de Tocar la Terminal

Nadie me lo explicó claramente, así que lo explico yo: hay **tres capas**, y confundirlas te va a costar horas.

- **OpenShell** — el sandbox. Piensa en él como un contenedor Linux blindado donde tu agente de IA realmente se ejecuta. Tiene su propio sistema de archivos, sus propias reglas de red, y no confía en nada por defecto.
- **NemoClaw** — la distribución del framework de agentes de Nvidia. Viene con inferencia optimizada para GPU y una API key de Nvidia para pruebas. ¿Esa key? Es solo para *testing*. No recibes ninguna advertencia cuando deja de funcionar.
- **OpenClaw** — el gateway que conecta tu sandbox a plataformas de chat (Telegram, Discord, etc.), programa cron jobs y gestiona el ciclo de vida del agente.

Si estás en Windows como yo, suma otra capa: **WSL → Docker → OpenShell sandbox**. Cuatro capas de profundidad. Un error en cualquier capa rompe todo el sistema.

## Políticas de Red: El Asesino Silencioso

El sandbox bloquea todo el tráfico saliente por defecto. Tienes que permitir *explícitamente* cada endpoint de API que tu agente va a usar. Es buena seguridad — pero también es la razón #1 por la que mi agente se quedaba ahí sin hacer nada durante horas mientras yo debuggeaba.

No entendía la sintaxis de las políticas. Me equivoqué con la indentación en archivos YAML. YAML no perdona errores de indentación. Un espacio de más y tu política falla silenciosamente.

## Reconstruir el Sandbox Borra Todo

Esta dolió. Ajustas una configuración del sandbox, reconstruyes, y todo tu trabajo dentro del sandbox desaparece. Cada script, cada credencial, cada archivo de configuración. Aprendes a externalizar todo rápido — o aprendes por las malas.

**Lección clave:** Mantén tu trabajo fuera del sandbox. Monta volúmenes. Haz backup de tus configuraciones. El sandbox es desechable por diseño.

## Lo Que Le Diría a Mi Yo de la Instalación #1

1. Dibuja la arquitectura en papel primero. En serio.
2. Guarda cada API key que generes. No puedo enfatizar esto lo suficiente.
3. Prueba las políticas de red un endpoint a la vez.
4. La indentación no es opcional en YAML. Usa un linter.
5. Asume que vas a reconstruir el sandbox al menos una vez. Prepárate para ello.

## La Conclusión

Hospedar tu propio agente de IA no es difícil porque la tecnología sea compleja. Es difícil porque la *superficie operativa* es grande — redes, contenedores, configuraciones, credenciales — y cada capa tiene bordes afilados. ¿La buena noticia? Una vez que entiendes la arquitectura y respetas el sandbox, todo hace clic. Y tener un agente de IA corriendo 24/7 en hardware que tú controlas genuinamente vale la pena.
