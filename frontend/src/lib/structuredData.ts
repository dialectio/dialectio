/** schema.org descriptions of our pages (JSON-LD): the site as a dataset, a word page as a
 * term with its words in other languages, a dialect page as a set of terms with breadcrumbs. */
import {
  type ConceptDetail,
  capitalize,
  type DialectDetail,
  type DialectWordDetail,
  inLocale,
  localized,
  meaningOf,
  SITE_URL,
} from "@/lib/api";

const CONTEXT = "https://schema.org";
const MAX_TERMS = 100; // words listed in one page's data

const site = (locale: string) => ({
  "@type": "DefinedTermSet",
  name: "Dialectio",
  url: `${SITE_URL}/${locale}`,
});

/** The home page: the website and its open data. */
export function siteData(locale: string, description: string) {
  const url = `${SITE_URL}/${locale}`;
  return {
    "@context": CONTEXT,
    "@graph": [
      { "@type": "WebSite", name: "Dialectio", url, inLanguage: locale, description },
      {
        "@type": "Dataset",
        name: "Dialectio",
        url,
        description,
        keywords: ["dialects", "dialectology", "lexicon", "IPA", "linguistic atlas"],
        isBasedOn: ["https://www.wikidata.org", "https://en.wiktionary.org"],
        creator: { "@type": "Organization", name: "Dialectio", url: SITE_URL },
      },
    ],
  };
}

/** A word page: the concept as a term, with its words in other languages and dialects. */
export function conceptData(concept: ConceptDetail, locale: string) {
  const name = localized(locale, concept.gloss_en, concept.gloss_uk, concept.glosses);
  const spellings = new Set<string>();
  for (const language of concept.languages) {
    for (const form of language.forms) spellings.add(form.spelling);
  }
  spellings.delete(name);
  return {
    "@context": CONTEXT,
    "@type": "DefinedTerm",
    name,
    description:
      inLocale(locale, concept.description_en, concept.description_uk, concept.descriptions) ??
      undefined,
    url: `${SITE_URL}/${locale}/word/${concept.slug}`,
    inLanguage: locale,
    alternateName: [...spellings].slice(0, MAX_TERMS),
    sameAs: concept.wikidata_id ? `https://www.wikidata.org/wiki/${concept.wikidata_id}` : undefined,
    inDefinedTermSet: site(locale),
  };
}

/** A dialect word page ("бараболя"): one term per meaning, described by its standard word. */
export function dialectWordData(entry: DialectWordDetail, locale: string) {
  const url = `${SITE_URL}/${locale}/slovo/${encodeURIComponent(entry.word.toLowerCase())}`;
  const terms = entry.meanings.map((meaning) => ({
    "@type": "DefinedTerm",
    name: entry.word,
    description: meaningOf(meaning, locale),
    url,
    inLanguage: locale,
    inDefinedTermSet: site(locale),
  }));
  return { "@context": CONTEXT, "@graph": terms };
}

/** A dialect page:its words (with the standard word as description) and breadcrumbs. */
export function dialectData(dialect: DialectDetail, locale: string, allDialects: string) {
  const name = capitalize(localized(locale, dialect.name_en, dialect.name_uk, dialect.names));
  const url = `${SITE_URL}/${locale}/dialects/${dialect.code}`;
  const regional = dialect.kind === "regional";
  const ukrainian = locale === "uk" && dialect.code.startsWith("ukr-");
  return {
    "@context": CONTEXT,
    "@graph": [
      {
        "@type": "DefinedTermSet",
        name,
        url,
        inLanguage: locale,
        hasDefinedTerm: dialect.words_list.slice(0, MAX_TERMS).map((word) => ({
          "@type": "DefinedTerm",
          name: word.spelling,
          // the meaning: the standard word only for Ukrainian dialects on Ukrainian pages
          description:
            (ukrainian && word.standard) ||
            localized(locale, word.gloss_en, word.gloss_uk, word.glosses),
          // the page the dialect page links the word to
          url:
            regional || word.standard?.toLowerCase() === word.spelling.toLowerCase()
              ? `${SITE_URL}/${locale}/word/${word.slug}`
              : `${SITE_URL}/${locale}/slovo/${encodeURIComponent(word.spelling.toLowerCase())}`,
        })),
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: allDialects, item: `${SITE_URL}/${locale}/dialects` },
          { "@type": "ListItem", position: 2, name, item: url },
        ],
      },
    ],
  };
}
