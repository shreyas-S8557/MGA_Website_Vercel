import Header from "@/components/Header";
import Hero from "@/components/Hero";
import RealResults from "@/components/RealResults";
import HowItWorks from "@/components/HowItWorks";
import GratitudeSection from "@/components/GratitudeSection";
import JourneySteps from "@/components/JourneySteps";
import MentorsSection from "@/components/MentorsSection";
import MentorStorySection from "@/components/MentorStorySection";
import Footer from "@/components/Footer";
import ScrollReveal from "@/components/ScrollReveal";

export default function HomePage() {
  return (
    <main>
      <Header />
      <Hero />
      <RealResults />
      <HowItWorks />
      <GratitudeSection />
      <JourneySteps />
      <MentorsSection />
      <MentorStorySection />
      <Footer />
      <ScrollReveal />
    </main>
  );
}
