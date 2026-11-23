-- A few listings so a fresh board is not empty. Runs once, like any migration.
INSERT INTO listings (title, description, category, condition, estimated_value, owner_name) VALUES
    (N'Denim jacket, size M', N'Worn one season, no stains.', 'clothing', 4, 35.00, N'Lucia'),
    (N'Calculus: Early Transcendentals', N'8th edition, some pencil notes.', 'books', 3, 40.00, N'Omar'),
    (N'Desk lamp with USB port', N'Warm and cold light, works perfectly.', 'home', 5, 18.00, N'Chen'),
    (N'Bluetooth speaker', N'Battery lasts about 6 hours.', 'electronics', 3, 30.00, N'Marta'),
    (N'Yoga mat', N'6 mm, barely used.', 'sports', 5, 15.00, N'Jonas'),
    (N'Scientific calculator', N'Casio fx-991, exam approved.', 'electronics', 4, 20.00, N'Aisha');
