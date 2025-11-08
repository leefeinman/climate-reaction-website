import { defineCollection, z } from "astro:content";

const baseFields = {
  title: z.string(),
  date: z.string().optional(),
  summary: z.string().optional(),
  tags: z.array(z.string()).default([]),
  heroImage: z.string().optional(),
  author: z.string().optional()
};

const md = defineCollection({
  type: "content",
  schema: z.object(baseFields)
});

export const collections = {
  explainers: md,
  roundups: md,
  actions: md,
  events: md,
  team: md
};
