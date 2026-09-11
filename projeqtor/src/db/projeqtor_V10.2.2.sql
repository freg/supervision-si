-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 10.2.2                                      //
-- // Date : 2023-01-26                                     //
-- ///////////////////////////////////////////////////////////
-- Patch on V10.2

CREATE INDEX layoutUser ON `${prefix}layout` (`idUser`);
CREATE INDEX layoutObjectClass ON `${prefix}layout` (`objectClass`);

CREATE INDEX layoutcolumnselectorLayout ON `${prefix}layoutcolumnselector` (`idLayout`);

CREATE INDEX layoutforcedObjectClass ON `${prefix}layoutforced` (`objectClass`);

CREATE INDEX layoutgroupuserLayoutGroup ON `${prefix}layoutgroupuser` (`idLayoutGroup`);
