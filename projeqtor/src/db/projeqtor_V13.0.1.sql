-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 13.0.1                                      //
-- // Date : 2026-06-29                                     //
-- ///////////////////////////////////////////////////////////
-- Patch on V13.0



UPDATE `${prefix}subtask` s left join `${prefix}userstory` a on s.refType='UserStory' and s.refId=a.id  SET s.idProject=a.idProject WHERE s.refType='UserStory' and s.idProject!=a.idProject;
UPDATE `${prefix}subtask` s left join `${prefix}activity` a on s.refType='Activity' and s.refId=a.id  SET s.idProject=a.idProject WHERE s.refType='Activity' and s.idProject!=a.idProject;
UPDATE `${prefix}subtask` s left join `${prefix}ticket` t on s.refType='Ticket' and s.refId=t.id  SET s.idProject=t.idProject WHERE s.refType='Ticket' and s.idProject!=t.idProject;