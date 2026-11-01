-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 12.1.3                                      //
-- // Date : 2025-05-15                                     //
-- ///////////////////////////////////////////////////////////

UPDATE `${prefix}expense` set scope='ProjectExpense' where scope is null and idActivity is null and idResource is null;
UPDATE `${prefix}expense` set scope='ActivityExpense' where scope is null and idActivity is not null and idResource is null;
UPDATE `${prefix}expense` set scope='IndividualExpense' where scope is null and idActivity is null and idResource is not null;
