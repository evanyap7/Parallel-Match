import { describe, expect, it } from "vitest";
import { en } from "./en";
import { LOCALES, fill, makeT } from "./index";
import { changeLabel, momentHeadline, whatIfQuestion, word } from "../model";

const holes = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe("locales", () => {
  it("covers the Americas, Europe and Asia", () => {
    expect(LOCALES.map((l) => l.code)).toEqual(
      expect.arrayContaining(["en", "es", "pt", "fr", "de", "it", "ja", "ko", "zh", "hi", "ar"]),
    );
    expect(LOCALES.find((l) => l.code === "ar")?.dir).toBe("rtl");
  });

  for (const locale of LOCALES) {
    it(`${locale.code} has every key with matching placeholders`, async () => {
      const messages = await locale.load();
      expect(Object.keys(messages).sort()).toEqual(Object.keys(en).sort());
      for (const key of Object.keys(en) as (keyof typeof en)[]) {
        expect(messages[key].trim(), `${locale.code} ${key} is empty`).not.toBe("");
        expect(holes(messages[key]), `${locale.code} ${key}`).toEqual(holes(en[key]));
        expect(messages[key], `${locale.code} ${key} has an em dash`).not.toContain("—");
      }
    });
  }
});

describe("translation helpers", () => {
  it("fills placeholders and keeps unknown ones", () => {
    expect(fill("a {x} b {y}", { x: 1 })).toBe("a 1 b {y}");
  });

  it("falls back to English for an unknown event word", () => {
    expect(word("some_new_type")).toBe("some new type");
  });

  it("translates model text through the translator", async () => {
    const es = makeT(await LOCALES.find((l) => l.code === "es")!.load());
    const pen = { id: "e", step: 1, t: 1, min: "56", period: 2, type: "foul", call: "penalty", team: "COP", score: [0, 0] as [number, number] };
    expect(momentHeadline(pen, es)).toBe("Penalti señalado contra Copperfield FC");
    expect(whatIfQuestion({ type: "flip_call" }, pen, es)).toBe("¿Y si no fuera penalti?");
    expect(changeLabel({ type: "card", card: "red" }, pen, es)).toBe("Mostrar tarjeta roja");
  });
});
