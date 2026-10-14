-- Marketing OS · versión 3: experimentos definidos en archivos de campaña (Fase 6)
-- Solo expande: la definición del experimento (grupos de piezas, métrica y criterio) se guarda como JSON.

ALTER TABLE experimento ADD COLUMN definicion TEXT NOT NULL DEFAULT '{}';
ALTER TABLE experimento ADD COLUMN decidido_en TEXT;
