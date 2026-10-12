-- PostgreSQL schema for Restaurant Intelligence Database v1
-- Synthetic development dataset. Do not present generated records as actual restaurant data.
CREATE TABLE IF NOT EXISTS customers (
  customer_id TEXT PRIMARY KEY,
  customer_segment TEXT NOT NULL,
  first_seen_date DATE NOT NULL,
  data_origin TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS menu_categories (
  category_id TEXT PRIMARY KEY,
  category_name TEXT NOT NULL UNIQUE,
  data_origin TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS menu_items (
  menu_item_id TEXT PRIMARY KEY,
  item_name TEXT NOT NULL UNIQUE,
  category_id TEXT NOT NULL REFERENCES menu_categories(category_id),
  list_price_inr NUMERIC(10,2) NOT NULL CHECK (list_price_inr >= 0),
  diet_type TEXT NOT NULL,
  is_available BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATE NOT NULL,
  data_origin TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS orders (
  order_id TEXT PRIMARY KEY,
  order_ts TIMESTAMP NOT NULL,
  order_date DATE NOT NULL,
  customer_id TEXT REFERENCES customers(customer_id),
  channel TEXT NOT NULL CHECK (channel IN ('dine_in','takeaway','delivery')),
  order_status TEXT NOT NULL CHECK (order_status IN ('completed','cancelled','refunded')),
  currency TEXT NOT NULL DEFAULT 'INR',
  subtotal_inr NUMERIC(12,2) NOT NULL CHECK (subtotal_inr >= 0),
  tax_inr NUMERIC(12,2) NOT NULL CHECK (tax_inr >= 0),
  service_charge_inr NUMERIC(12,2) NOT NULL CHECK (service_charge_inr >= 0),
  total_inr NUMERIC(12,2) NOT NULL CHECK (total_inr >= 0),
  data_origin TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS order_items (
  order_item_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  menu_item_id TEXT NOT NULL REFERENCES menu_items(menu_item_id),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price_inr NUMERIC(10,2) NOT NULL CHECK (unit_price_inr >= 0),
  discount_inr NUMERIC(10,2) NOT NULL CHECK (discount_inr >= 0),
  line_total_inr NUMERIC(12,2) NOT NULL CHECK (line_total_inr >= 0),
  data_origin TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS payments (
  payment_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(order_id),
  payment_ts TIMESTAMP NOT NULL,
  payment_method TEXT NOT NULL,
  payment_status TEXT NOT NULL CHECK (payment_status IN ('paid','voided','refunded')),
  amount_inr NUMERIC(12,2) NOT NULL CHECK (amount_inr >= 0),
  refund_amount_inr NUMERIC(12,2) NOT NULL CHECK (refund_amount_inr >= 0),
  data_origin TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS reviews (
  review_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(order_id),
  reviewed_menu_item_id TEXT NOT NULL REFERENCES menu_items(menu_item_id),
  review_date DATE NOT NULL,
  rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  review_text TEXT NOT NULL,
  sentiment_label TEXT NOT NULL,
  issue_category TEXT NOT NULL,
  data_origin TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS ingredients (
  ingredient_id TEXT PRIMARY KEY,
  ingredient_name TEXT NOT NULL UNIQUE,
  unit TEXT NOT NULL,
  ingredient_category TEXT NOT NULL,
  data_origin TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS menu_recipes (
  recipe_id TEXT PRIMARY KEY,
  menu_item_id TEXT NOT NULL REFERENCES menu_items(menu_item_id),
  ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
  quantity_per_portion NUMERIC(12,3) NOT NULL CHECK (quantity_per_portion > 0),
  unit TEXT NOT NULL,
  data_origin TEXT NOT NULL DEFAULT 'SYNTHETIC',
  UNIQUE(menu_item_id, ingredient_id)
);
CREATE TABLE IF NOT EXISTS stock_movements (
  movement_id TEXT PRIMARY KEY,
  movement_ts TIMESTAMP NOT NULL,
  ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
  movement_type TEXT NOT NULL CHECK (movement_type IN ('opening_balance','purchase_receipt','sale_consumption','adjustment')),
  quantity_delta NUMERIC(14,3) NOT NULL,
  unit TEXT NOT NULL,
  source_order_id TEXT REFERENCES orders(order_id),
  source_order_item_id TEXT REFERENCES order_items(order_item_id),
  reference_note TEXT,
  data_origin TEXT NOT NULL DEFAULT 'SYNTHETIC',
  CHECK ((movement_type <> 'sale_consumption') OR (quantity_delta < 0 AND source_order_id IS NOT NULL AND source_order_item_id IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS inventory (
  ingredient_id TEXT PRIMARY KEY REFERENCES ingredients(ingredient_id),
  on_hand_quantity NUMERIC(14,3) NOT NULL CHECK (on_hand_quantity >= 0),
  reorder_level NUMERIC(14,3) NOT NULL CHECK (reorder_level >= 0),
  unit TEXT NOT NULL,
  last_count_date DATE NOT NULL,
  data_origin TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS documents (
  document_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  document_type TEXT NOT NULL,
  version TEXT NOT NULL,
  effective_date DATE NOT NULL,
  body TEXT NOT NULL,
  data_origin TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_chunks (
  chunk_id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(document_id),
  chunk_index INTEGER NOT NULL,
  chunk_text TEXT NOT NULL,
  source_title TEXT NOT NULL,
  source_version TEXT NOT NULL,
  embedding_status TEXT NOT NULL,
  data_origin TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_findings (
  finding_id TEXT PRIMARY KEY,
  agent_name TEXT NOT NULL,
  finding_title TEXT NOT NULL,
  finding_text TEXT NOT NULL,
  metric_name TEXT,
  metric_value NUMERIC,
  period_start DATE,
  period_end DATE,
  evidence_table TEXT NOT NULL,
  evidence_query_id TEXT NOT NULL,
  evidence_record_ids TEXT NOT NULL,
  confidence NUMERIC(4,3) CHECK (confidence BETWEEN 0 AND 1),
  created_at TIMESTAMP NOT NULL,
  data_origin TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_date_status ON orders(order_date, order_status);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_menu ON order_items(menu_item_id);
CREATE INDEX IF NOT EXISTS idx_reviews_rating_date ON reviews(rating, review_date);
CREATE INDEX IF NOT EXISTS idx_stock_movements_ingredient_ts ON stock_movements(ingredient_id, movement_ts);
CREATE INDEX IF NOT EXISTS idx_stock_movements_source_item ON stock_movements(source_order_item_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_document ON document_chunks(document_id);
