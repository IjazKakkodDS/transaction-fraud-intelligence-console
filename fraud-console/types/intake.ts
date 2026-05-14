import { z } from "zod";

export const IntakePayloadSchema = z.object({
  transaction_id: z.string().min(1),
  user_id: z.string().min(1),
  merchant_id: z.string().min(1),
  amount: z.coerce.number().positive(),
  currency: z.string().length(3),
  payment_method: z.string().min(1),
  timestamp: z.string().min(1),
  country: z.string().length(2),
  city: z.string().optional(),
  device_id: z.string().optional(),
  ip_address: z.string().optional(),
  device_type: z.string().optional(),
  merchant_category: z.string().optional(),
  is_international: z.boolean().optional(),
});

export type IntakePayload = z.infer<typeof IntakePayloadSchema>;
