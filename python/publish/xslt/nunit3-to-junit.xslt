<?xml version="1.0" encoding="utf-8"?>
<!-- based on https://github.com/nunit/nunit-transforms/blob/caadb5442cb1da0a3ade5a03cf169c3e1a13ac57/nunit3-junit/nunit3-junit.xslt -->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="xml" indent="yes"/>

  <xsl:template match="/test-run | /test-results">
    <xsl:variable name="skipped">
      <xsl:choose>
        <xsl:when test="@skipped"><xsl:value-of select="@skipped"/></xsl:when>
        <xsl:otherwise>0</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:variable name="not-run">
      <xsl:choose>
        <xsl:when test="@not-run"><xsl:value-of select="@not-run"/></xsl:when>
        <xsl:otherwise>0</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:variable name="ignored">
      <xsl:choose>
        <xsl:when test="@ignored"><xsl:value-of select="@ignored"/></xsl:when>
        <xsl:otherwise>0</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <testsuites tests="{@testcasecount | @total}" failures="{@failed | @failures}" skipped="{$skipped + $not-run + $ignored}">
      <xsl:if test="@errors">
        <xsl:attribute name="errors"><xsl:value-of select="@errors"/></xsl:attribute>
      </xsl:if>
      <xsl:if test="@duration">
        <xsl:attribute name="time"><xsl:value-of select="@duration"/></xsl:attribute>
      </xsl:if>
      <xsl:apply-templates/>
    </testsuites>
  </xsl:template>

  <xsl:template match="test-suite">
    <testsuite>
      <xsl:if test="@testcasecount">
        <xsl:attribute name="tests"><xsl:value-of select="@testcasecount"/></xsl:attribute>
      </xsl:if>
      <xsl:if test="@failed">
        <xsl:attribute name="failures"><xsl:value-of select="@failed"/></xsl:attribute>
      </xsl:if>
      <xsl:if test="@errors">
        <xsl:attribute name="errors"><xsl:value-of select="@errors"/></xsl:attribute>
      </xsl:if>
      <xsl:if test="@skipped">
        <xsl:attribute name="skipped"><xsl:value-of select="@skipped"/></xsl:attribute>
      </xsl:if>
      <xsl:if test="@duration or @time">
        <xsl:attribute name="time">
          <xsl:choose>
            <xsl:when test="@duration"><xsl:value-of select="@duration"/></xsl:when>
            <xsl:when test="@time"><xsl:value-of select="@time"/></xsl:when>
          </xsl:choose>
        </xsl:attribute>
      </xsl:if>
      <xsl:if test="@start-time">
        <xsl:attribute name="timestamp"><xsl:value-of select="@start-time"/></xsl:attribute>
      </xsl:if>
      <xsl:attribute name="name">
        <xsl:choose>
          <xsl:when test="@fullname"><xsl:value-of select="@fullname"/></xsl:when>
          <xsl:when test="@classname"><xsl:value-of select="@classname"/></xsl:when>
          <xsl:otherwise>
            <xsl:for-each select="ancestor::test-suite[@type='TestSuite' or @type='Namespace']/@name">
              <xsl:value-of select="concat(., '.')"/>
            </xsl:for-each>
            <xsl:value-of select="@name"/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:attribute>
      <xsl:apply-templates/>
    </testsuite>
  </xsl:template>

  <xsl:template match="test-case">
    <testcase name="{@name}" classname="{classname}">
      <xsl:if test="@result">
        <xsl:attribute name="status"><xsl:value-of select="@result"/></xsl:attribute>
      </xsl:if>
      <xsl:if test="@assertions">
        <xsl:attribute name="assertions"><xsl:value-of select="@assertions"/></xsl:attribute>
      </xsl:if>
      <xsl:if test="@duration or @time">
        <xsl:attribute name="time">
          <xsl:choose>
            <xsl:when test="@duration"><xsl:value-of select="@duration"/></xsl:when>
            <xsl:when test="@time"><xsl:value-of select="@time"/></xsl:when>
            <xsl:otherwise>0</xsl:otherwise>
          </xsl:choose>
        </xsl:attribute>
      </xsl:if>
      <xsl:if test="@executed = 'False' or @result = 'Skipped' or @result = 'Ignored' or @result = 'NotRunnable' or @result = 'Inconclusive' or @runstate = 'Skipped' or @runstate = 'Ignored' or @runstate = 'NotRunnable'">
        <skipped>
          <xsl:if test="reason/message != ''"><xsl:attribute name="message"><xsl:value-of select="reason/message"/></xsl:attribute></xsl:if>
        </skipped>
      </xsl:if>
      <xsl:apply-templates/>
    </testcase>
  </xsl:template>

  <xsl:template match="command-line"/>
  <xsl:template match="settings"/>
  <xsl:template match="filter"/>

  <xsl:template match="output">
    <system-out>
      <xsl:value-of select="."/>
    </system-out>
  </xsl:template>

  <xsl:template match="stack-trace">
  </xsl:template>

  <xsl:template match="test-case/failure">
    <xsl:if test="parent::test-case[not(@result) or @result != 'Error']">
      <failure message="{./message}">
        <xsl:value-of select="./stack-trace"/>
      </failure>
    </xsl:if>
    <xsl:if test="parent::test-case[@result='Error']">
      <error message="{./message}">
        <xsl:value-of select="./stack-trace"/>
      </error>
    </xsl:if>
  </xsl:template>

  <xsl:template match="test-suite/failure"/>

  <xsl:template match="test-case/reason"/>

  <xsl:template match="test-case/assertions">
  </xsl:template>

  <xsl:template match="test-suite/reason"/>

  <xsl:template match="properties"/>
</xsl:stylesheet>